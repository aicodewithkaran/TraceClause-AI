import os
from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "TraceClause AI"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment Control: "production", "staging", "development", or "test"
    ENVIRONMENT: str = "production"
    
    # Strict Development-Only Demo Mode (Must be False in production)
    ALLOW_DEMO_AUTH: bool = False
    
    # Core Secret Key (Must be at least 32 chars in production)
    SECRET_KEY: str = ""
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

    # Supabase Database & Auth Keys
    SUPABASE_URL: Optional[str] = ""
    SUPABASE_KEY: Optional[str] = ""
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = ""
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = ""
    SUPABASE_SECRET_KEY: Optional[str] = ""
    SUPABASE_JWKS_URL: Optional[str] = ""

    @property
    def supabase_anon_key(self) -> str:
        return self.SUPABASE_KEY or self.SUPABASE_PUBLISHABLE_KEY or ""

    @property
    def supabase_admin_key(self) -> str:
        return self.SUPABASE_SERVICE_ROLE_KEY or self.SUPABASE_SECRET_KEY or ""
    
    # Razorpay Payment Gateway & Webhook (Stripe removed)
    RAZORPAY_KEY_ID: Optional[str] = ""
    RAZORPAY_KEY_SECRET: Optional[str] = ""
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = ""
    RAZORPAY_SOLO_LINK: Optional[str] = "https://razorpay.com"
    RAZORPAY_TEAM_LINK: Optional[str] = "https://razorpay.com"

    # Document Upload Hardening Limits
    MAX_UPLOAD_SIZE_MB: int = 15
    MAX_PAGE_COUNT: int = 100
    MAX_ZIP_ENTRIES: int = 500
    MAX_DECOMPRESSED_SIZE_MB: int = 50
    MAX_COMPRESSION_RATIO: float = 20.0
    PARSER_TIMEOUT_SECONDS: int = 15

    class Config:
        env_file = ".env"
        case_sensitive = True

    def validate_security_configuration(self):
        """
        Enforce strict fail-safe security assertions at application startup.
        Prevents starting with weak secrets, missing keys, or demo authentication enabled in production.
        """
        env = self.ENVIRONMENT.lower()
        if env not in ("production", "staging", "development", "test"):
            raise RuntimeError(f"FATAL: Unrecognized ENVIRONMENT '{self.ENVIRONMENT}'. Must be 'production', 'staging', 'development', or 'test'.")

        if env in ("production", "staging"):
            # 1. Assert demo authentication is completely disabled
            if self.ALLOW_DEMO_AUTH:
                raise RuntimeError("FATAL SECURITY MISCONFIGURATION: ALLOW_DEMO_AUTH cannot be True in production or staging.")

            # 2. Assert SECRET_KEY is set and strong
            if not self.SECRET_KEY or self.SECRET_KEY in ("supersecretkey", "secret", "changeme", "default") or len(self.SECRET_KEY) < 32:
                raise RuntimeError("FATAL SECURITY MISCONFIGURATION: SECRET_KEY must be a cryptographically secure key of at least 32 characters in production.")

            # 3. Assert Supabase keys are configured
            if not self.SUPABASE_URL or not self.supabase_anon_key:
                raise RuntimeError("FATAL SECURITY MISCONFIGURATION: SUPABASE_URL and SUPABASE_KEY / SUPABASE_PUBLISHABLE_KEY must be configured in production.")
            
            if not self.supabase_admin_key:
                raise RuntimeError("FATAL SECURITY MISCONFIGURATION: SUPABASE_SERVICE_ROLE_KEY / SUPABASE_SECRET_KEY is required for server-side operations in production.")

            # 4. Assert at least one LLM API key is present
            if not (self.OPENAI_API_KEY or self.GEMINI_API_KEY or self.ANTHROPIC_API_KEY):
                raise RuntimeError("FATAL SECURITY MISCONFIGURATION: At least one AI provider API key (OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY) must be set.")

settings = Settings()
