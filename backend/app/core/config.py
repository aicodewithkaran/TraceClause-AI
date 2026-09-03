from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "TraceClause AI"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str = "supersecretkey"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Provider Selection: "openai", "gemini", or "anthropic" (Auto-detected if blank)
    LLM_PROVIDER: Optional[str] = ""
    
    # API Keys for all 3 supported providers
    OPENAI_API_KEY: Optional[str] = ""
    GEMINI_API_KEY: Optional[str] = ""
    ANTHROPIC_API_KEY: Optional[str] = ""
    
    # Default LLM model names
    OPENAI_MODEL: str = "gpt-4o"
    GEMINI_MODEL: str = "gemini-1.5-pro"
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20240620"
    
    # Dual Embedding Engine Options: "openai", "gemini", or auto-detect
    EMBEDDING_PROVIDER: Optional[str] = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"

    # Database Keys
    SUPABASE_URL: Optional[str] = ""
    SUPABASE_KEY: Optional[str] = ""
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = ""
    
    # Payment Gateway Keys & Hosted Payment Links
    STRIPE_SECRET_KEY: Optional[str] = ""
    STRIPE_WEBHOOK_SECRET: Optional[str] = ""
    RAZORPAY_KEY_ID: Optional[str] = ""
    RAZORPAY_KEY_SECRET: Optional[str] = ""
    RAZORPAY_SOLO_LINK: Optional[str] = "https://razorpay.com"
    RAZORPAY_TEAM_LINK: Optional[str] = "https://razorpay.com"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
