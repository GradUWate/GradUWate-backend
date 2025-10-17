
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Base configuration for the API (no secrets here)."""
    ENV: str = Field(default="local")
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    # Placeholder DB URL; swap to Postgres later (e.g., postgresql+asyncpg://user:pass@host:5432/dbname)
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./dev.db")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
