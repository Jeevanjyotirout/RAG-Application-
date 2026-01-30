from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_path: str = "observability.db"


settings = Settings()
