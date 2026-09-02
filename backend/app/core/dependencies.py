from fastapi import Depends, HTTPException, status
from app.core.security import get_current_user, supabase_client

TIER_PERMISSIONS = {
    "free": {
        "risk_score_clause_extraction",
        "plain_english_explanations"
    },
    "solo": {
        "risk_score_clause_extraction",
        "plain_english_explanations",
        "ai_redline_generation",
        "docx_export",
        "rag_interactive_chat"
    },
    "team": {
        "risk_score_clause_extraction",
        "plain_english_explanations",
        "ai_redline_generation",
        "docx_export",
        "rag_interactive_chat",
        "workspace_management",
        "custom_playbook_rules"
    }
}

async def get_current_profile(current_user = Depends(get_current_user)) -> dict:
    """
    Retrieves user profile from public.profiles table including subscription tier and quota details.
    """
    user_id = current_user.id
    try:
        res = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        if res.data and len(res.data) > 0:
            profile = res.data[0]
            profile["auth_user"] = current_user
            return profile
        else:
            # Fallback default profile if record not found yet
            return {
                "id": user_id,
                "email": getattr(current_user, "email", ""),
                "subscription_tier": "free",
                "lifetime_free_audits_used": 0,
                "monthly_quota_used": 0,
                "auth_user": current_user
            }
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return {
            "id": user_id,
            "email": getattr(current_user, "email", ""),
            "subscription_tier": "free",
            "lifetime_free_audits_used": 0,
            "monthly_quota_used": 0,
            "auth_user": current_user
        }

def require_feature(feature_name: str):
    """
    FastAPI dependency guard to enforce tier-based authorization.
    Returns HTTP 403 Forbidden if user's subscription tier does not permit the feature.
    """
    async def dependency(current_profile: dict = Depends(get_current_profile)):
        user_tier = current_profile.get("subscription_tier") or "free"
        allowed_features = TIER_PERMISSIONS.get(user_tier, set())
        if feature_name not in allowed_features:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: '{feature_name}' requires an active Solo or Team plan."
            )
        return current_profile
    return dependency
