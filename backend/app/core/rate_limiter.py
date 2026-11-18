import time
import logging
from collections import defaultdict
from typing import Dict, List
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

        # Get client IP address (respecting X-Forwarded-For if set behind proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
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
    """Tracks estimated monthly AI provider spend and alerts/trips when budget limit is reached."""
    def __init__(self, monthly_budget_usd: float = 250.0):
        self.monthly_budget_usd = monthly_budget_usd
        self.estimated_spend_usd = 0.0

    def record_usage(self, estimated_cost: float):
        self.estimated_spend_usd += estimated_cost
        if self.estimated_spend_usd >= self.monthly_budget_usd:
            logger.critical(f"MONTHLY AI BUDGET HARD LIMIT REACHED: ${self.estimated_spend_usd:.2f} >= ${self.monthly_budget_usd:.2f}!")
        elif self.estimated_spend_usd >= self.monthly_budget_usd * 0.8:
            logger.warning(f"AI Provider spend alert: ${self.estimated_spend_usd:.2f} is at 80% of monthly budget limit.")

    def is_budget_exceeded(self) -> bool:
        return self.estimated_spend_usd >= self.monthly_budget_usd

budget_tracker = BudgetTracker(monthly_budget_usd=settings.MONTHLY_AI_BUDGET_HARD_LIMIT_USD)
