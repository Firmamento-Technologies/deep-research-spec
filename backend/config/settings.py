"""Application settings from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

# Get backend directory path
BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application configuration from environment."""
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://drs:drs@localhost/drs",
        alias="DATABASE_URL",
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379",
        alias="REDIS_URL",
    )
    
    # LLM APIs
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_site_url: str = Field(default="", alias="OPENROUTER_SITE_URL")
    openrouter_site_name: str = Field(default="", alias="OPENROUTER_SITE_NAME")
    brave_api_key: str = Field(default="", alias="BRAVE_API_KEY")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    
    # MinIO Object Storage
    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="deep-research", alias="MINIO_BUCKET")
    
    # Budget & Limits
    max_budget: float = Field(default=50.0, alias="MAX_BUDGET")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # RLM (Recursive Language Models)
    rlm_mode: bool = Field(default=False, alias="RLM_MODE")
    rlm_environment: str = Field(default="local", alias="RLM_ENVIRONMENT")
    rlm_sandbox: str = Field(default="local", alias="RLM_SANDBOX")
    rlm_log_dir: str = Field(default="./logs/rlm", alias="RLM_LOG_DIR")
    rlm_allow_tier_upgrade: bool = Field(default=False, alias="RLM_ALLOW_TIER_UPGRADE")
    
    # Runtime environment
    app_env: str = Field(default="dev", alias="APP_ENV")

    # JWT Authentication
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    
    # CORS
    allowed_origins: str = Field(default="", alias="ALLOWED_ORIGINS")
    
    # Debug
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Concurrency
    max_concurrent_runs: int = Field(default=5, alias="MAX_CONCURRENT_RUNS")
    

    @model_validator(mode="after")
    def _validate_security_policy(self):
        if self.app_env.lower() in {"prod", "production"} and not self.jwt_secret_key:
            raise ValueError("JWT_SECRET_KEY is required when APP_ENV=production")
        return self

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
