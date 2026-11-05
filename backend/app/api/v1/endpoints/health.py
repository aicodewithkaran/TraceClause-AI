import time
from fastapi import APIRouter, Response, status
from app.core.config import settings
from supabase import create_client

router = APIRouter()

def _get_supabase_client():
    if settings.SUPABASE_URL and settings.supabase_admin_key:
        return create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
    if settings.SUPABASE_URL and settings.supabase_anon_key:
        return create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
    return None

@router.get("/live")
def liveness_probe():
    """
    Lightweight Liveness Probe:
    Used by orchestrators (Render, Kubernetes) to verify process responsiveness.
    Never connects to databases or external AI APIs. Responds in < 5ms.
    """
    return {
        "status": "alive",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": int(time.time())
    }

@router.get("/ready")
def readiness_probe(response: Response):
    """
    Readiness Probe:
    Verifies that required database connections are operational and accepting queries.
    Never calls external AI APIs to prevent false outages and cost spikes.
    Sanitizes all errors without exposing internal database credentials or stack traces.
    """
    supabase = _get_supabase_client()
    if not supabase:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "database": "not_configured"
        }

    try:
        # 1. Fast database connectivity verification (SELECT 1 equivalent)
        db_start = time.time()
        supabase.table("profiles").select("id").limit(1).execute()
        db_latency_ms = round((time.time() - db_start) * 1000, 2)

        # 2. Queue depth observation
        queue_count = 0
        try:
            q_res = supabase.table("contract_analysis_jobs") \
                .select("id", count="exact") \
                .in_("status", ["queued", "processing"]) \
                .limit(1) \
                .execute()
            queue_count = q_res.count or 0
        except Exception:
            pass

        return {
            "status": "ready",
            "database": "connected",
            "db_latency_ms": db_latency_ms,
            "active_queue_depth": queue_count,
            "environment": settings.ENVIRONMENT
        }
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "database": "connection_failed",
            "error": "Database readiness check failed"
        }

