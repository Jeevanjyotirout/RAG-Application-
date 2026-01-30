from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid

from . import db

class RequestLogEntry(BaseModel):
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    trace_id: Optional[str] = None
    question: str
    answer: Optional[str] = None
    latency_ms_total: int = 0
    latency_ms_retrieval: int = 0
    latency_ms_llm: int = 0
    retrieved_sources: List[Dict[str, Any]] = []
    retrieved_distances: Optional[List[float]] = None
    prompt_tokens: Optional[int] = None
    answer_tokens: Optional[int] = None
    error: Optional[str] = None

def log_request(log_entry: RequestLogEntry):
    """Registra i dettagli di una richiesta nel database."""
    db.insert_log(
        request_id=str(log_entry.request_id),
        question=log_entry.question,
        answer=log_entry.answer,
        latency_ms_total=log_entry.latency_ms_total,
        latency_ms_retrieval=log_entry.latency_ms_retrieval,
        latency_ms_llm=log_entry.latency_ms_llm,
        retrieved_sources=log_entry.retrieved_sources,
        retrieved_distances=log_entry.retrieved_distances,
        prompt_tokens=log_entry.prompt_tokens,
        answer_tokens=log_entry.answer_tokens,
        error=log_entry.error,
        trace_id=log_entry.trace_id,
    )
