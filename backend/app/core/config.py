from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # MongoDB
    MONGODB_URI: str
    MONGODB_DB_NAME: str = "rush_dev"
    
    # Redis
    REDIS_URL: str
    
    # Weaviate
    WEAVIATE_URL: str
    WEAVIATE_GRPC_PORT: str
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Pydantic V2 설정
    model_config = SettingsConfigDict(
        env_file="../.env",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()