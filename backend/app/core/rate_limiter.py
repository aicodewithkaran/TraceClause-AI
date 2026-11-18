import time
import logging
from collections import defaultdict
from typing import Dict, List, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.config import settings

logger = logging.getLogger("rate_limiter")

class SlidingWindowLimiter:
    """In-memory sliding window rate limiter."""
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history: Dict[str, List[float]] = defaultdict(list)
        self.last_cleanup = time.time()

    def is_allowed(self, key: str) -> bool:
        if settings.ENVIRONMENT.lower() == "test":
            return True

        now = time.time()
        # Periodic cleanup of keys older than window
        if now - self.last_cleanup > 120:
            self._cleanup(now)

        window_start = now - self.window_seconds
        # Filter out timestamps outside the active window
        timestamps = [ts for ts in self.history[key] if ts > window_start]
        if len(timestamps) >= self.max_requests:
            self.history[key] = timestamps
            return False

        timestamps.append(now)
        self.history[key] = timestamps
        return True

    def _cleanup(self, now: float):
        self.last_cleanup = now
        cutoff = now - self.window_seconds
        stale_keys = []
        for key, ts_list in self.history.items():
            valid = [t for t in ts_list if t > cutoff]
            if not valid:
                stale_keys.append(key)
            else:
                self.history[key] = valid
        for k in stale_keys:
            del self.history[k]

class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying per-IP request rate limiting across all API endpoints.
    Excludes public health probes, API docs, and root status checks.
    
    NOTE ON ARCHITECTURE:
    This is an in-memory sliding-window limiter designed as a lightweight guard
    for the single-worker Beta launch phase (100-500 MAU).
    For multi-instance horizontal scaling, upgrade to an external Redis/Upstash token bucket.
    """
    def __init__(self, app, max_requests_per_minute: int = 60):
        super().__init__(app)
        self.limiter = SlidingWindowLimiter(max_requests=max_requests_per_minute, window_seconds=60)
        self.excluded_paths = {"/", "/health/ready", "/health/live", "/docs", "/openapi.json", f"{settings.API_V1_STR}/health/ready", f"{settings.API_V1_STR}/health/live"}

    async def dispatch(self, request: Request, call_next):
        if settings.ENVIRONMENT.lower() == "test":
            return await call_next(request)

        path = request.url.path
        if path in self.excluded_paths or request.method == "OPTIONS":
            return await call_next(request)

        # Sanitize IP extraction: prioritize X-Real-IP from reverse proxy,
        # then rightmost untampered client IP from X-Forwarded-For, then socket host
        client_ip = request.headers.get("x-real-ip")
        if not client_ip:
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
                client_ip = ips[-1] if ips else None
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        if not self.limiter.is_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip} on path {path}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Too many requests. Please slow down and try again in 1 minute."
                }
            )

        return await call_next(request)

# User-level action limiter (e.g. max uploads per minute per user)
upload_rate_limiter = SlidingWindowLimiter(
    max_requests=settings.MAX_UPLOADS_PER_MINUTE_PER_USER,
    window_seconds=60
)

class BudgetTracker:
    """
    Tracks cumulative estimated AI provider spend and alerts/trips when budget limit is reached.
    Stops further model calls if monthly hard limit is exceeded.
    """
    def __init__(self, monthly_budget_usd: float = 250.0):
        self.monthly_budget_usd = monthly_budget_usd
        self.estimated_spend_usd = 0.0

    def record_usage(self, estimated_cost: float):
        self.estimated_spend_usd += max(0.0, float(estimated_cost))
        if self.estimated_spend_usd >= self.monthly_budget_usd:
            logger.critical(
                f"MONTHLY AI BUDGET HARD LIMIT REACHED: ${self.estimated_spend_usd:.4f} >= ${self.monthly_budget_usd:.2f} USD! "
                "Circuit breaker tripped."
            )
        elif self.estimated_spend_usd >= (self.monthly_budget_usd * 0.8):
            logger.warning(
                f"AI Provider spend alert: ${self.estimated_spend_usd:.4f} USD is at 80%+ of monthly budget limit."
            )

    def is_budget_exceeded(self) -> bool:
        return self.estimated_spend_usd >= self.monthly_budget_usd

    def get_stats(self) -> Dict[str, Any]:
        return {
            "estimated_spend_usd": round(self.estimated_spend_usd, 4),
            "monthly_budget_usd": self.monthly_budget_usd,
            "budget_exceeded": self.is_budget_exceeded()
        }

budget_tracker = BudgetTracker(monthly_budget_usd=settings.MONTHLY_AI_BUDGET_HARD_LIMIT_USD)
