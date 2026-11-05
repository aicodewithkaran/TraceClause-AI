from fastapi import Header, HTTPException, status
from typing import Optional
from pydantic import BaseModel
from supabase import create_client, Client
from app.core.config import settings

# Initialize Supabase Admin client with Service Role Key for token verification & user management
supabase_admin: Optional[Client] = (
    create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
    if (settings.SUPABASE_URL and settings.supabase_admin_key)
    else None
)
supabase_anon: Optional[Client] = (
    create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
    if (settings.SUPABASE_URL and settings.supabase_anon_key)
    else None
)
supabase_client: Optional[Client] = supabase_admin or supabase_anon

class DemoUser(BaseModel):
    id: str = "demo-user-id"
    email: str = "demo@traceclause.ai"

class AuthenticatedUser(BaseModel):
    id: str
    email: Optional[str] = None

async def get_current_user(authorization: Optional[str] = Header(None)) -> AuthenticatedUser:
    """
    FastAPI security dependency to validate Supabase JWT tokens.
    Fails closed: Any missing, malformed, expired, or invalid token raises HTTP 401 Unauthorized.
    Distinguishes invalid credentials (401) from authentication service outages (503).
    Demo user access is strictly restricted to development/test environments behind ALLOW_DEMO_AUTH.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided. Authorization header required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    parts = authorization.strip().split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = parts[1]

    # Handle development-only demo tokens
    if token in ("demo-token", "guest-token", "dev-token"):
        if settings.ALLOW_DEMO_AUTH and settings.ENVIRONMENT.lower() in ("development", "test"):
            return AuthenticatedUser(id="demo-user-id", email="demo@traceclause.ai")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo tokens are disabled in this environment.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    client_to_use = supabase_admin or supabase_anon
    if not client_to_use:
        # If database/auth client cannot be initialized
        if settings.ALLOW_DEMO_AUTH and settings.ENVIRONMENT.lower() in ("development", "test"):
            return AuthenticatedUser(id="demo-user-id", email="demo@traceclause.ai")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable. Please check system configuration."
        )

    try:
        user_response = client_to_use.auth.get_user(token)
        if user_response and hasattr(user_response, 'user') and user_response.user:
            u = user_response.user
            user_id = getattr(u, 'id', None)
            user_email = getattr(u, 'email', None)
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication token did not contain a valid user identity.",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            return AuthenticatedUser(id=str(user_id), email=user_email)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e).lower()
        # Distinguish network/connection/outage errors from invalid token errors
        if any(term in err_msg for term in ("connect", "timeout", "network", "refused", "unavailable", "dns")):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication provider is temporarily unreachable. Please try again shortly."
            )
        # Any other failure from get_user is an invalid/expired token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
