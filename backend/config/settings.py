from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://drs:drs_dev_password@localhost:5432/drs"
    redis_url: str = "redis://localhost:6379"
    minio_url: str = "http://localhost:9000"
    minio_access_key: str = "drs_admin"
    minio_secret_key: str = "drs_secret_key"
    openrouter_api_key: str = ""
    companion_model: str = "anthropic/claude-sonnet-4-6"

    class Config:
        env_file = ".env"


settings = Settings()
