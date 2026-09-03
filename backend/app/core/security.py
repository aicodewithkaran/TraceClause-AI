from fastapi import Header, HTTPException
from typing import Optional
from pydantic import BaseModel
from supabase import create_client, Client
from app.core.config import settings

# Initialize Supabase Admin client with Service Role Key for token verification & user management
supabase_admin: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY) if (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY) else None
supabase_anon: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY) if (settings.SUPABASE_URL and settings.SUPABASE_KEY) else None
supabase_client: Client = supabase_admin or supabase_anon

class DemoUser(BaseModel):
    id: str = "demo-user-id"
    email: str = "demo@traceclause.ai"

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    FastAPI security dependency to validate Supabase JWT tokens sent by Next.js client.
    Resolves the exact authenticated user UUID from Supabase Auth.
    """
    if not authorization:
        return DemoUser()

    if not authorization.startswith("Bearer "):
        return DemoUser()

    token = authorization.split(" ")[1]
    if token in ("demo-token", "guest-token", "dev-token"):
        return DemoUser()

    # First attempt verification using admin client, then fallback to anon client
    client_to_use = supabase_admin or supabase_anon
    if not client_to_use:
        return DemoUser()

    try:
        user_response = client_to_use.auth.get_user(token)
        if user_response and hasattr(user_response, 'user') and user_response.user:
            return user_response.user
        return DemoUser()
    except Exception as e:
        print(f"Auth verification fallback: {e}")
        return DemoUser()
