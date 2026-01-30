import time
import uuid
from typing import List

import chromadb
import httpx
from loguru import logger
from opentelemetry import trace

from app.observability.logger import RequestLogEntry, log_request
from app.rag.tokenizer import count_tokens
from app.config import settings

# Get a tracer for this module
tracer = trace.get_tracer(__name__)

def embed_query(text: str) -> List[float]:
    """Calculates the embedding of a single query with Ollama."""
    with httpx.Client() as client:
        resp = client.post(
            settings.ollama_embed_url,
            json={"model": settings.embed_model, "input": text},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings")
        if not embeddings:
            raise RuntimeError("No embeddings returned from Ollama")
        return embeddings[0]


async def rag_query(question: str):
    """Executes a RAG query on the FED reports, measuring performance and logging the details."""
    t_start = time.perf_counter()
    log_entry = RequestLogEntry(question=question)
    
    # Get the trace_id from the current span
    current_span = trace.get_current_span()
    if current_span.get_span_context().is_valid:
        trace_id = current_span.get_span_context().trace_id
        log_entry.trace_id = format(trace_id, '032x')

    try:
        logger.info(f"RAG query: {question!r} (request_id: {log_entry.request_id})")

        # 1) Measure the retrieval latency (embedding + search)
        with tracer.start_as_current_span("DB Vector Search") as span:
            t_retrieval_start = time.perf_counter()
            q_emb = embed_query(question)
            client = chromadb.PersistentClient(path=settings.chroma_path)
            collection = client.get_collection("fed_reports")
            results = collection.query(
                query_embeddings=[q_emb],
                n_results=4,
                include=["documents", "metadatas", "distances"],
            )
            t_retrieval_end = time.perf_counter()
            log_entry.latency_ms_retrieval = round((t_retrieval_end - t_retrieval_start) * 1000)
            span.set_attribute("latency_ms", log_entry.latency_ms_retrieval)

        retrieved_docs = results["documents"][0]
        log_entry.retrieved_sources = results["metadatas"][0]
        log_entry.retrieved_distances = results["distances"][0]
        
        context_chunks = []
        for doc, meta, dist in zip(retrieved_docs, log_entry.retrieved_sources, log_entry.retrieved_distances):
            context_chunks.append(
                f"From {meta.get('source_file')} (chunk {meta.get('chunk_index')}), distance={dist:.4f}:\n{doc}"
            )
        context = "\n\n---\n\n".join(context_chunks)

        prompt = f"""
You are an assistant who answers based on the following excerpts from the Federal Reserve's (FED) annual performance reports.

Context:
{context}

Question: {question}

Instructions:
- Answer clearly and concisely.
- If possible, indicate which report/year you are referring to (even just by mentioning it in the text).
- If the context does not contain enough information to answer reliably, state it explicitly.
Answer:
"""

        # 2) Measure the LLM call latency and estimate the tokens
        with tracer.start_as_current_span("LLM Generation") as span:
            log_entry.prompt_tokens = count_tokens(prompt)
            t_llm_start = time.perf_counter()
            async with httpx.AsyncClient() as client_http:
                resp = await client_http.post(
                    settings.ollama_gen_url,
                    json={"model": settings.gen_model, "prompt": prompt, "stream": False},
                    timeout=300,
                )
                resp.raise_for_status()
                data = resp.json()
                log_entry.answer = data.get("response", "").strip()
            t_llm_end = time.perf_counter()
            log_entry.latency_ms_llm = round((t_llm_end - t_llm_start) * 1000)
            log_entry.answer_tokens = count_tokens(log_entry.answer)
            span.set_attribute("latency_ms", log_entry.latency_ms_llm)
            span.set_attribute("prompt_tokens", log_entry.prompt_tokens)
            span.set_attribute("answer_tokens", log_entry.answer_tokens)


        return {
            "request_id": str(log_entry.request_id),
            "answer": log_entry.answer,
            "retrieved": log_entry.retrieved_sources,
        }

    except Exception as e:
        logger.error(f"Error during RAG query {log_entry.request_id}: {e}")
        log_entry.error = str(e)
        # Re-raise the exception to be handled by FastAPI (which will turn it into a 500)
        raise

    finally:
        t_end = time.perf_counter()
        log_entry.latency_ms_total = round((t_end - t_start) * 1000)
        log_request(log_entry)
        logger.info(f"Completed RAG query {log_entry.request_id} in {log_entry.latency_ms_total}ms")
