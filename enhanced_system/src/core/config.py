"""Configuration settings for the enhanced system"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:@localhost:5432/idsyaruat"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # PostgreSQL connection for psycopg2
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "idsyaruat"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    
    # Performance
    BATCH_SIZE: int = 1000
    PARALLEL_WORKERS: int = 4
    CACHE_TTL: int = 3600
    
    # API
    API_VERSION: str = "v1"
    API_PREFIX: str = "/api"
    DEBUG: bool = True
    
    # Monitoring
    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = False
    
    class Config:
        env_file = ".env"


settings = Settings()