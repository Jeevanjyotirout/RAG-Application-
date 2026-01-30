from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import Optional

from app.rag.query import rag_query
from app.observability.db import init_db, insert_feedback
from app.observability.tracing import setup_tracer
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to be executed at application startup
    init_db()
    setup_tracer()  # Set up the OpenTelemetry tracer
    HTTPXClientInstrumentor().instrument()
    yield
    # Code to be executed at shutdown (not necessary in this case)

class QueryRequest(BaseModel):
    question: str

class RatingRequest(BaseModel):
    request_id: str
    rating: int = Field(..., ge=1, le=5) # Ensures the rating is between 1 and 5
    comment: Optional[str] = None


app = FastAPI(title="RAG Observability - v1 demo", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)


@app.get("/")
def root():
    return {"status": "ok", "message": "RAG FED reports API v1"}


@app.post("/query")
async def query_endpoint(payload: QueryRequest):
    result = await rag_query(payload.question)
    return result

@app.post("/rate")
async def rate_endpoint(payload: RatingRequest):
    try:
        insert_feedback(
            request_id=payload.request_id,
            rating=payload.rating,
            comment=payload.comment
        )
        return {"status": "ok", "message": "Feedback successfully recorded."}
    except Exception as e:
        # In a real app, we would log the error here
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
