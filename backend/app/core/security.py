from fastapi import Header, HTTPException, Depends
from typing import Optional
from supabase import create_client, Client
from app.core.config import settings

# Initialize Supabase client
supabase_client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    FastAPI security dependency to validate Supabase JWT tokens sent by Next.js client.
    Enforces user isolation so users can only access their own data.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format. Must be Bearer <token>")

    token = authorization.split(" ")[1]

    try:
        # Verify token with Supabase Auth Engine
        user_response = supabase_client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        return user_response.user
    except Exception as e:
        print(f"Auth verification error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
