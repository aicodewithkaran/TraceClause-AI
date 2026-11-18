import uuid
import logging
from typing import Optional, Dict, Any
from app.core.config import settings
from supabase import create_client, Client

logger = logging.getLogger("ai_budget")

# Pricing in integer microdollars ($1 USD = 1,000,000 microdollars)
MODEL_PRICING = {
    "gpt-4o": {
        "input_microdollars_per_token": 2.5,    # $2.50 / 1M tokens
        "output_microdollars_per_token": 10.0,  # $10.00 / 1M tokens
        "default_max_output_tokens": 4000
    },
    "gemini-1.5-pro": {
        "input_microdollars_per_token": 1.25,   # $1.25 / 1M tokens
        "output_microdollars_per_token": 5.0,   # $5.00 / 1M tokens
        "default_max_output_tokens": 4000
    },
    "claude-3-5-sonnet-20240620": {
        "input_microdollars_per_token": 3.0,    # $3.00 / 1M tokens
        "output_microdollars_per_token": 15.0,  # $15.00 / 1M tokens
        "default_max_output_tokens": 4000
    },
    "text-embedding-3-small": {
        "input_microdollars_per_token": 0.02,   # $0.02 / 1M tokens
        "output_microdollars_per_token": 0.0,
        "default_max_output_tokens": 0
    },
    "models/text-embedding-004": {
        "input_microdollars_per_token": 0.0,    # Included tier
        "output_microdollars_per_token": 0.0,
        "default_max_output_tokens": 0
    }
}

class AIBudgetService:
    """
    Durable, Concurrency-Safe AI Budget Ledger Service.
    - Interacts directly with PostgreSQL stored procedures with table locks.
    - Prevents race conditions across multiple API and worker processes.
    - Uses integer microdollars to prevent floating-point rounding errors.
    """

    def __init__(self, supabase: Optional[Client] = None):
        if supabase:
            self.supabase = supabase
        elif settings.SUPABASE_URL and settings.supabase_admin_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
        elif settings.SUPABASE_URL and settings.supabase_anon_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
        else:
            self.supabase = None

        # Hard limit converted to microdollars ($250 USD = 250,000,000 microdollars)
        self.cap_microdollars = int(settings.MONTHLY_AI_BUDGET_HARD_LIMIT_USD * 1_000_000)

    @classmethod
    def estimate_cost_microdollars(cls, model: str, prompt_text: str, max_output_tokens: Optional[int] = None) -> int:
        """Estimates maximum plausible cost in microdollars for a prompt and model with conservative safety bounds."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gemini-1.5-pro"])
        
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            tokens_in = max(1, len(enc.encode(prompt_text)))
        except Exception:
            tokens_in = max(1, int(len(prompt_text) / 3.5))

        tokens_out = max_output_tokens if max_output_tokens is not None else pricing["default_max_output_tokens"]
        
        cost = (tokens_in * pricing["input_microdollars_per_token"]) + (tokens_out * pricing["output_microdollars_per_token"])
        return max(100, int(cost))  # Minimum 100 microdollars ($0.0001)

    @classmethod
    def calculate_actual_cost_microdollars(cls, model: str, tokens_in: int, tokens_out: int) -> int:
        """Calculates actual cost in microdollars from token counts."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gemini-1.5-pro"])
        cost = (tokens_in * pricing["input_microdollars_per_token"]) + (tokens_out * pricing["output_microdollars_per_token"])
        return max(10, int(cost))

    def reserve(
        self, 
        reservation_id: str, 
        estimated_microdollars: int, 
        provider: str, 
        model: str, 
        job_id: Optional[str] = None
    ) -> bool:
        """
        Atomically checks budget ceiling and reserves estimated spend via PostgreSQL FOR UPDATE.
        Fails closed if budget would be exceeded.
        """
        if not self.supabase:
            return True  # Dev mode fallback when database is not connected

        try:
            res = self.supabase.rpc("reserve_ai_budget", {
                "p_reservation_id": reservation_id,
                "p_estimated_microdollars": estimated_microdollars,
                "p_provider": provider,
                "p_model": model,
                "p_job_id": job_id,
                "p_cap_microdollars": self.cap_microdollars
            }).execute()

            data = res.data or {}
            if not data.get("success"):
                logger.critical(
                    f"AI BUDGET CEILING ENFORCED: Reservation {reservation_id} rejected. "
                    f"Requested {estimated_microdollars} microdollars exceeds cap."
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Error reserving AI budget: {e}")
            # Fail closed on database ledger failure to prevent runaway spend
            return False

    def settle(
        self, 
        reservation_id: str, 
        actual_microdollars: int, 
        status: str = "settled", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Releases reserved amount and records actual spend in the durable ledger.
        Idempotent by reservation_id.
        """
        if not self.supabase:
            return True

        try:
            res = self.supabase.rpc("settle_ai_budget", {
                "p_reservation_id": reservation_id,
                "p_actual_microdollars": actual_microdollars,
                "p_status": status,
                "p_metadata": metadata or {}
            }).execute()
            data = res.data or {}
            return bool(data.get("success"))
        except Exception as e:
            logger.error(f"Error settling AI budget reservation {reservation_id}: {e}")
            return False

    def release(self, reservation_id: str, reason: str = "cancelled") -> bool:
        """
        Releases reserved amount when a request is cancelled or definitely unbillable.
        Idempotent by reservation_id.
        """
        if not self.supabase:
            return True

        try:
            res = self.supabase.rpc("release_ai_budget", {
                "p_reservation_id": reservation_id,
                "p_reason": reason
            }).execute()
            data = res.data or {}
            return bool(data.get("success"))
        except Exception as e:
            logger.error(f"Error releasing AI budget reservation {reservation_id}: {e}")
            return False

ai_budget_service = AIBudgetService()

