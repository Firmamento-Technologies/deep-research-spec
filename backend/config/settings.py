"""Application settings from environment variables."""

import os
from pydantic_settings import BaseSettings
from pydantic import Field


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
    brave_api_key: str = Field(default="", alias="BRAVE_API_KEY")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    
    # CORS
    allowed_origins: str = Field(default="", alias="ALLOWED_ORIGINS")
    
    # Debug
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Concurrency
    max_concurrent_runs: int = Field(default=5, alias="MAX_CONCURRENT_RUNS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
