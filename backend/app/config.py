from functools import lru_cache
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "EmailAI"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/emailai"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Encryption
    ENCRYPTION_KEY: str = ""  # base64-encoded 32-byte Fernet key

    # File Storage
    STORAGE_PATH: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 50

    # Public base URL (used to build open-tracking pixel links in outbound mail)
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Email notification for alerts
    ADMIN_ALERT_EMAIL: str = ""

    # ARQ Worker
    WORKER_MAX_JOBS: int = 10
    POLL_INTERVAL_SECONDS: int = 300  # 5 min fallback polling

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def check_encryption_key(cls, v: str) -> str:
        if v and len(v) < 32:
            raise ValueError("ENCRYPTION_KEY must be a valid Fernet key (base64, 44 chars)")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
