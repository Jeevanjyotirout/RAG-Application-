from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    chroma_path: str = "chroma_db"
    ollama_embed_url: str = "http://localhost:11434/api/embed"
    embed_model: str = "nomic-embed-text"
    ollama_gen_url: str = "http://localhost:11434/api/generate"
    gen_model: str = "llama3.1"
    db_path: str = "observability.db"


settings = Settings()
