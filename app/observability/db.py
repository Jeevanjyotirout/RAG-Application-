import sqlite3
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from loguru import logger
from app.config import settings

DB_PATH = Path(settings.db_path).resolve()

def _add_column_if_not_exists(cursor, table_name, column_name, column_type):
    """Aggiunge una colonna a una tabella se non esiste già."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]
    if column_name not in columns:
        logger.info(f"Aggiunta colonna '{column_name}' alla tabella '{table_name}'...")
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

def init_db():
    """Inizializza il database e crea/aggiorna le tabelle se necessario."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Crea la tabella di log delle richieste
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            request_id TEXT NOT NULL UNIQUE,
            question TEXT NOT NULL,
            answer TEXT,
            latency_ms_total INTEGER,
            latency_ms_retrieval INTEGER,
            latency_ms_llm INTEGER,
            retrieved_sources TEXT,
            error TEXT
        )
    """)
    
    # Aggiunge nuove colonne per la migrazione dello schema
    _add_column_if_not_exists(cursor, "requests_log", "retrieved_distances", "TEXT")
    _add_column_if_not_exists(cursor, "requests_log", "prompt_tokens", "INTEGER")
    _add_column_if_not_exists(cursor, "requests_log", "answer_tokens", "INTEGER")
    _add_column_if_not_exists(cursor, "requests_log", "trace_id", "TEXT")

    # Crea la tabella di feedback
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            FOREIGN KEY (request_id) REFERENCES requests_log (request_id)
        )
    """)
    
    conn.commit()
    conn.close()

def insert_log(
    request_id: str,
    question: str,
    answer: Optional[str],
    latency_ms_total: int,
    latency_ms_retrieval: int,
    latency_ms_llm: int,
    retrieved_sources: List[Dict[str, Any]],
    retrieved_distances: Optional[List[float]],
    prompt_tokens: Optional[int],
    answer_tokens: Optional[int],
    error: Optional[str],
    trace_id: Optional[str]
):
    """Inserisce un record di log nel database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO requests_log (
            request_id, question, answer, latency_ms_total, 
            latency_ms_retrieval, latency_ms_llm, retrieved_sources, 
            retrieved_distances, prompt_tokens, answer_tokens, error, trace_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_id,
            question,
            answer,
            latency_ms_total,
            latency_ms_retrieval,
            latency_ms_llm,
            json.dumps(retrieved_sources),
            json.dumps(retrieved_distances) if retrieved_distances is not None else None,
            prompt_tokens,
            answer_tokens,
            error,
            trace_id,
        ),
    )
    conn.commit()
    conn.close()

def insert_feedback(request_id: str, rating: int, comment: Optional[str]):
    """Inserisce o aggiorna un feedback per una data richiesta."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Usa INSERT OR REPLACE per gestire casi in cui si vota più volte la stessa richiesta
    cursor.execute(
        """
        INSERT OR REPLACE INTO request_feedback (request_id, rating, comment)
        VALUES (?, ?, ?)
        """,
        (request_id, rating, comment),
    )
    conn.commit()
    conn.close()

# Esegui l'inizializzazione all'avvio del modulo
# init_db()
