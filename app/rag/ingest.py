import os
import re
from typing import List

import chromadb
import httpx
import fitz  # PyMuPDF
from loguru import logger

CHROMA_PATH = "chroma_db"
DATA_DIR = "./app/data/fed_reports"

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"  # modello di embedding che hai già in Ollama


def extract_pdf_text(path: str) -> str:
    """Estrae il testo da un PDF usando PyMuPDF (fitz) e pulisce i caratteri problematici."""
    doc = fitz.open(path)
    pages_text: List[str] = []
    for page in doc:
        try:
            text = page.get_text() or ""
            # Sostituisce il non-breaking space con uno spazio normale
            text = text.replace('\xa0', ' ')
            # Sostituisce sequenze di due o più punti con uno spazio
            text = re.sub(r'\.{2,}', ' ', text)
            pages_text.append(text)
        except Exception as e:
            logger.warning(f"Errore estraendo testo da {path}, pagina {page.number}: {e}")
            pages_text.append("")
    doc.close()
    return "\n".join(pages_text)


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """Spezzetta il testo in chunk con overlap."""
    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap

    return chunks


def embed_chunks(chunks: List[str], batch_size: int = 32) -> List[List[float]]:
    """Calcola gli embedding per una lista di chunk usando Ollama, in batch."""
    logger.info(f"Calcolo embedding per {len(chunks)} chunk con {EMBED_MODEL}...")
    all_embeddings: List[List[float]] = []
    
    with httpx.Client() as client:
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            logger.info(f"Processo batch {i // batch_size + 1}/{(len(chunks) + batch_size - 1) // batch_size}...")
            
            resp = client.post(
                OLLAMA_EMBED_URL,
                json={"model": EMBED_MODEL, "input": batch},
                timeout=600,
            )
            resp.raise_for_status()
            
            data = resp.json()
            batch_embeddings = data.get("embeddings", [])
            
            if len(batch_embeddings) != len(batch):
                raise RuntimeError(
                    f"Numero di embedding ({len(batch_embeddings)}) diverso dai chunk nel batch ({len(batch)})"
                )
            
            all_embeddings.extend(batch_embeddings)

    if len(all_embeddings) != len(chunks):
        raise RuntimeError(
            f"Numero totale di embedding ({len(all_embeddings)}) diverso dai chunk ({len(chunks)})"
        )
        
    return all_embeddings


def ingest_documents():
    """Ingerisce i PDF in data/fed_reports, crea chunk, calcola embedding e li salva in Chroma."""
    logger.info("Inizio ingestion dei documenti FED...")

    if not os.path.isdir(DATA_DIR):
        raise FileNotFoundError(f"Cartella dati non trovata: {DATA_DIR}")

    # Prepara client Chroma
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        name="fed_reports",
        metadata={"hnsw:space": "cosine"},
    )

    all_docs: List[str] = []
    all_ids: List[str] = []
    all_metadatas: List[dict] = []

    for fname in os.listdir(DATA_DIR):
        if not fname.lower().endswith(".pdf"):
            continue

        full_path = os.path.join(DATA_DIR, fname)
        logger.info(f"Estrazione testo da {full_path}...")
        full_text = extract_pdf_text(full_path)

        chunks = chunk_text(full_text)
        logger.info(f"{fname}: creati {len(chunks)} chunk.")

        base_id = os.path.splitext(fname)[0]
        for i, chunk in enumerate(chunks):
            doc_id = f"{base_id}_chunk_{i}"
            all_docs.append(chunk)
            all_ids.append(doc_id)
            all_metadatas.append(
                {
                    "source_file": fname,
                    "chunk_index": i,
                }
            )

    if not all_docs:
        logger.warning("Nessun documento trovato da ingerire.")
        return

    logger.info(f"Totale chunk da ingerire: {len(all_docs)}")

    embeddings = embed_chunks(all_docs)

    logger.info("Scrittura dei chunk e embedding in Chroma...")
    collection.add(
        documents=all_docs,
        embeddings=embeddings,
        ids=all_ids,
        metadatas=all_metadatas,
    )

    logger.info("Ingestion completata con successo!")
