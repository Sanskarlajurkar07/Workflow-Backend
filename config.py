from pydantic_settings import BaseSettings
from typing import Optional, List

class Settings(BaseSettings):
    # Debug and environment settings
    DEBUG: bool = False
    ENV: str = "development"
    
    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "flowmind"
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    
    # Qdrant settings
    QDRANT_URL: str = ""
    QDRANT_API_KEY: Optional[str] = None
    
    # JWT settings
    JWT_SECRET_KEY: str = "your-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OAuth2 settings
    OAUTH2_SECRET: str = "your-oauth2-secret"
    GOOGLE_CLIENT_ID: str = "placeholder"
    GOOGLE_CLIENT_SECRET: str = "placeholder"
    AIRTABLE_CLIENT_ID: Optional[str] = None
    AIRTABLE_CLIENT_SECRET: Optional[str] = None
    GITHUB_CLIENT_ID: str = "placeholder"
    GITHUB_CLIENT_SECRET: str = "placeholder"
    GITHUB_APP_CLIENT_ID: Optional[str] = None
    GITHUB_APP_CLIENT_SECRET: Optional[str] = None
    # Separate GitHub OAuth app for workflow nodes
    GITHUB_WORKFLOW_CLIENT_ID: str = "Ov23litIYPS9dbF6xKgX"
    GITHUB_WORKFLOW_CLIENT_SECRET: str = "cae274de4f16a2def36d2cbcf87fbf95bfd99609"
    # HubSpot OAuth settings
    HUBSPOT_CLIENT_ID: str = "cbecf41d-26a0-4c8c-b78d-7c3ff4a84250"
    HUBSPOT_CLIENT_SECRET: str = "c1910040-c624-4fb5-a32e-438ef09b07d8"
    FRONTEND_URL: str = "http://localhost:5174"
    
    # Rate limiting settings
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost", "http://localhost:80"]
    
    # AI Model API Keys 
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None
    PERPLEXITY_API_KEY: Optional[str] = None
    XAI_API_KEY: Optional[str] = None
    
    # AWS Bedrock Settings
    AWS_ACCESS_KEY: Optional[str] = None
    AWS_SECRET_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    
    # Azure OpenAI Settings
    AZURE_API_KEY: Optional[str] = None
    AZURE_ENDPOINT: Optional[str] = None
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra fields to be ignored instead of forbidden

settings = Settings()