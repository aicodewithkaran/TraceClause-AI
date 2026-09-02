from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import HTTPException
from app.core.config import settings
from supabase import create_client, Client

FREE_TIER_LIFETIME_LIMIT = 3
SOLO_TIER_MONTHLY_LIMIT = 20
TEAM_TIER_MONTHLY_LIMIT = 100

class QuotaService:
    """Service to track, check, and reset user/workspace quota limits per subscription tier."""

    @staticmethod
    def get_supabase_client() -> Client:
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return None

    @classmethod
    def check_and_increment_quota(cls, user_id: str) -> Dict[str, Any]:
        client = cls.get_supabase_client()
        if not client:
            return {"quota_used": 0, "limit": FREE_TIER_LIFETIME_LIMIT, "tier": "free"}

        try:
            # Fetch user profile
            res = client.from_("profiles").select("*").eq("id", user_id).single().execute()
            profile = res.data

            if not profile:
                return {"quota_used": 0, "limit": FREE_TIER_LIFETIME_LIMIT, "tier": "free"}

            tier = (profile.get("subscription_tier") or "free").lower()
            
            if tier == "free":
                lifetime_used = profile.get("lifetime_free_audits_used", 0)
                if lifetime_used >= FREE_TIER_LIFETIME_LIMIT:
                    raise HTTPException(
                        status_code=429,
                        detail="Free trial limit reached (3/3 contracts). Please upgrade to Solo or Team."
                    )
                new_lifetime_used = lifetime_used + 1
                client.from_("profiles").update({
                    "lifetime_free_audits_used": new_lifetime_used
                }).eq("id", user_id).execute()

                return {
                    "quota_used": new_lifetime_used,
                    "limit": FREE_TIER_LIFETIME_LIMIT,
                    "tier": "free",
                    "remaining": FREE_TIER_LIFETIME_LIMIT - new_lifetime_used
                }

            # Paid Tiers (Solo or Team)
            limit = SOLO_TIER_MONTHLY_LIMIT if tier == "solo" else TEAM_TIER_MONTHLY_LIMIT
            last_reset = profile.get("last_quota_reset") or profile.get("last_reset_date")
            monthly_used = profile.get("monthly_quota_used", 0)

            # Check 30-day quota reset
            if last_reset:
                try:
                    reset_date = datetime.fromisoformat(last_reset.replace("Z", "+00:00"))
                    if datetime.now(reset_date.tzinfo) > reset_date + timedelta(days=30):
                        monthly_used = 0
                        client.from_("profiles").update({
                            "monthly_quota_used": 0,
                            "last_quota_reset": datetime.now().isoformat()
                        }).eq("id", user_id).execute()
                except Exception as ex:
                    print(f"Error parsing reset date: {ex}")

            # For Team tier, aggregate workspace pooled quota if applicable
            target_profile_id = user_id
            if tier == "team":
                # Check if user is in a workspace
                wm_res = client.from_("workspace_members").select("workspace_id").eq("user_id", user_id).execute()
                if wm_res.data and len(wm_res.data) > 0:
                    ws_id = wm_res.data[0]["workspace_id"]
                    # Get workspace owner profile to pool usage
                    ws_res = client.from_("workspaces").select("owner_id").eq("id", ws_id).execute()
                    if ws_res.data and len(ws_res.data) > 0:
                        target_profile_id = ws_res.data[0]["owner_id"]
                        if target_profile_id != user_id:
                            owner_prof = client.from_("profiles").select("monthly_quota_used").eq("id", target_profile_id).single().execute()
                            if owner_prof.data:
                                monthly_used = owner_prof.data.get("monthly_quota_used", 0)

            if monthly_used >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Monthly contract review limit reached. Upgrade or purchase quota overage."
                )

            new_monthly_used = monthly_used + 1
            client.from_("profiles").update({
                "monthly_quota_used": new_monthly_used
            }).eq("id", target_profile_id).execute()

            return {
                "quota_used": new_monthly_used,
                "limit": limit,
                "tier": tier,
                "remaining": limit - new_monthly_used
            }
        except HTTPException:
            raise
        except Exception as e:
            print(f"Quota check error: {e}")
            return {"quota_used": 0, "limit": FREE_TIER_LIFETIME_LIMIT, "tier": "free"}
