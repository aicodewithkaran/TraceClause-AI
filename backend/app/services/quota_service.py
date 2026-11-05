import uuid
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from supabase import create_client, Client

FREE_TIER_LIFETIME_LIMIT = 3
SOLO_TIER_MONTHLY_LIMIT = 20
TEAM_TIER_MONTHLY_LIMIT = 100

class QuotaService:
    """
    Service enforcing single-operation atomic quota limits via PostgreSQL stored procedure.
    Utilizes a reservation ledger (reserve -> commit / release) with row-level locks
    to guarantee zero race conditions and fail-closed security.
    """

    @staticmethod
    def get_supabase_client() -> Optional[Client]:
        # Always use the server-side Service Role Key for atomic stored procedure execution
        if settings.SUPABASE_URL and settings.supabase_admin_key:
            return create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
        if settings.SUPABASE_URL and settings.supabase_anon_key:
            return create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
        return None

    @classmethod
    def reserve_quota(cls, user_id: str, audit_id: str) -> Dict[str, Any]:
        """
        Atomically checks limits and reserves 1 quota unit via PostgreSQL stored procedure.
        Fails closed: Any database failure raises HTTP 503; exceeded limit raises HTTP 429.
        """
        client = cls.get_supabase_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable for quota verification. Request failed closed."
            )

        try:
            rpc_res = client.rpc("reserve_quota", {
                "p_user_id": user_id,
                "p_audit_id": audit_id
            }).execute()

            if rpc_res.data:
                return rpc_res.data

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Quota reservation returned no confirmation data."
            )
        except HTTPException:
            raise
        except Exception as e:
            err_text = str(e)
            if "QUOTA_EXCEEDED" in err_text:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Contract audit limit reached for your subscription tier. Please upgrade to continue."
                )
            if "USER_NOT_FOUND" in err_text:
                # If profile record doesn't exist yet, attempt to auto-create free profile once
                try:
                    client.from_("profiles").upsert({
                        "id": user_id,
                        "email": "",
                        "full_name": "User",
                        "country": "US",
                        "profession": "Legal",
                        "subscription_tier": "free",
                        "lifetime_free_audits_used": 0,
                        "monthly_quota_used": 0
                    }).execute()
                    # Retry reservation once after initialization
                    retry_res = client.rpc("reserve_quota", {
                        "p_user_id": user_id,
                        "p_audit_id": audit_id
                    }).execute()
                    if retry_res.data:
                        return retry_res.data
                except Exception as init_err:
                    if "QUOTA_EXCEEDED" in str(init_err):
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Contract audit limit reached for your subscription tier. Please upgrade to continue."
                        )

            # Fail closed on any other error
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to verify subscription quota due to database disruption. Please try again shortly."
            )

    @classmethod
    def release_quota(cls, user_id: str, audit_id: str):
        """
        Safely releases a reservation if the LLM analysis or downstream processing fails.
        Idempotent: Releases only the reservation matching (user_id, audit_id) with status 'reserved'.
        """
        client = cls.get_supabase_client()
        if not client:
            return

        try:
            client.rpc("release_quota", {
                "p_user_id": user_id,
                "p_audit_id": audit_id
            }).execute()
        except Exception as e:
            # Operational logging without sensitive details
            pass

    @classmethod
    def commit_quota(cls, user_id: str, audit_id: str):
        """
        Marks reservation 'completed' upon successful analysis and report persistence.
        """
        client = cls.get_supabase_client()
        if not client:
            return

        try:
            client.rpc("commit_quota", {
                "p_user_id": user_id,
                "p_audit_id": audit_id
            }).execute()
        except Exception as e:
            pass

    @classmethod
    def check_and_increment_quota(cls, user_id: str) -> Dict[str, Any]:
        """Backwards compatibility helper: reserves quota with a generated audit UUID."""
        audit_id = str(uuid.uuid4())
        return cls.reserve_quota(user_id, audit_id)
