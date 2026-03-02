import os
from functools import lru_cache


class Settings:
    """Runtime configuration read from environment variables."""

    def __init__(self) -> None:
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://drs:drs_dev_password@localhost:5432/drs",
        )
        # SQLAlchemy async requires the asyncpg driver prefix
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.database_url: str = db_url
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.minio_url: str = os.getenv("MINIO_URL", "http://localhost:9000")
        self.minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "drs_admin")
        self.minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "drs_secret_key")
        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
