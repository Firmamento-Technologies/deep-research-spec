import os

# Pydantic Settings — full implementation in STEP 5
# Reads from environment variables injected by docker-compose

class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://drs:drs_dev_password@localhost:5432/drs")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    minio_url: str = os.getenv("MINIO_URL", "http://localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "drs_admin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "drs_secret_key")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")

settings = Settings()
