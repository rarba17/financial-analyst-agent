# core/config.py
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # v2-style config; loads .env and IGNORES unknown keys (prevents crash you saw)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # <- key change: tolerate extra env vars like db_path, METADATA_PATH, etc.
    )

    # App meta
    PROJECT_NAME: str = "Demo App"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "dev"   # you had this twice; keep one
    WORKERS: int = 2
    PORT: int = 8000

    # PostgreSQL settings (required)
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int = 5432

    # Email / Azure
    AZURE_COMMUNICATION_CONNECTION_STRING: str
    AZURE_EMAIL_SENDER: str

    SECRET_KEY: str

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8501"]

    # Admin
    ADMIN_EMAIL: str
    ADMIN_OTP: str

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRY_MINUTES: str
    JWT_REFRESH_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_DAYS: int

    # LangChain / OpenAI
    LANGCHAIN_API_KEY: str
    LANGSMITH_TRACING: Optional[bool] = False
    LANGCHAIN_PROJECT: Optional[str] = "hoad-bi-dev"

    LLM_MODEL_NAME: str
    USE_AZURE_OPENAI: bool = True
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str
    AZURE_OPENAI_DEPLOYMENT_NAME: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_CHANNEL: str = "godrej_broadcast_channel"

    OPENAI_API_KEY: str

    # Build a SQLAlchemy URL from POSTGRES_* (defaults to psycopg v3 driver)
    @property
    def DATABASE_URL(self) -> str:
        driver = "psycopg"  # change to "psycopg2" only if you really use psycopg2-binary
        return (
            f"postgresql+{driver}://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

@lru_cache
def get_settings() -> Settings:
    return Settings()

# Backwards-compat: many files likely do `from core.config import settings`
# Keep this alias, but it's cached and safe with extra="ignore".
settings = get_settings()
