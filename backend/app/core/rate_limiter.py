import time
import uuid
import logging
import ipaddress
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.config import settings

logger = logging.getLogger("rate_limiter")

# Atomic Sliding-Window Lua Script for Redis
LUA_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

local clear_before = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)
local current_requests = redis.call('ZCARD', key)

if current_requests < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, math.ceil(window) + 5)
    return {1, limit - current_requests - 1, 0}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 1
    if oldest and #oldest >= 2 then
        local oldest_ts = tonumber(oldest[2])
        retry_after = math.max(1, math.ceil(oldest_ts + window - now))
    end
    return {0, 0, retry_after}
end
"""

class RateLimiterOutageError(Exception):
    """Raised when Redis rate limiter is unavailable and fail-closed policy is active."""
    pass


def _is_trusted_proxy_peer(peer_ip: str, trusted_proxies: List[str]) -> bool:
    if "*" in trusted_proxies or peer_ip in trusted_proxies:
        return True
    try:
        peer_addr = ipaddress.ip_address(peer_ip)
        for entry in trusted_proxies:
            if "/" in entry:
                net = ipaddress.ip_network(entry, strict=False)
                if peer_addr in net:
                    return True
    except Exception:
        pass
    return False

def get_trusted_client_ip(request: Request) -> str:
    """
    Safely extracts the authoritative client IP address respecting trusted reverse proxies.

    Security Assertions:
    1. Direct peer IP (socket host) is the authoritative network peer.
    2. If peer IP is NOT in settings.TRUSTED_PROXIES (and not '*'):
       Client-supplied headers (X-Forwarded-For, X-Real-IP) are UNTRUSTED and completely ignored.
    3. If peer IP IS in settings.TRUSTED_PROXIES (supports exact IP and CIDR subnets e.g. 10.0.0.0/8):
       - Checks X-Real-IP (set and overwritten by trusted reverse proxy like Render or Cloudflare).
       - Or inspects X-Forwarded-For and takes the rightmost (last) untampered IP before the trusted proxy.
    """
    peer_ip = request.client.host if request.client else "unknown"

    trusted_proxies = getattr(settings, "TRUSTED_PROXIES", ["127.0.0.1", "::1"])
    is_trusted_peer = _is_trusted_proxy_peer(peer_ip, trusted_proxies)

    if not is_trusted_peer:
        # Direct untrusted connection: client could forge any header. Trust ONLY socket IP.
        return peer_ip

    # Arrived via verified trusted reverse proxy: extract proxy-sanitized client IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
        if ips:
            return ips[-1]

    return peer_ip


class SlidingWindowLimiter:
    """In-memory sliding window rate limiter (used for fallback & test mode)."""
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history: Dict[str, List[float]] = defaultdict(list)
        self.last_cleanup = time.time()

    def check(self, key: str, limit: Optional[int] = None, window: Optional[int] = None) -> Tuple[bool, int, int]:
        max_req = limit or self.max_requests
        win_sec = window or self.window_seconds
        now = time.time()

        if now - self.last_cleanup > 120:
            self._cleanup(now)

        window_start = now - win_sec
        timestamps = [ts for ts in self.history[key] if ts > window_start]

        if len(timestamps) >= max_req:
            self.history[key] = timestamps
            oldest_ts = timestamps[0] if timestamps else now
            retry_after = max(1, int(oldest_ts + win_sec - now))
            return False, 0, retry_after

        timestamps.append(now)
        self.history[key] = timestamps
        remaining = max_req - len(timestamps)
        return True, remaining, 0

    def is_allowed(self, key: str) -> bool:
        allowed, _, _ = self.check(key)
        return allowed

    def _cleanup(self, now: float):
        self.last_cleanup = now
        cutoff = now - self.window_seconds
        stale_keys = [k for k, ts_list in self.history.items() if not any(t > cutoff for t in ts_list)]
        for k in stale_keys:
            del self.history[k]


class SharedRateLimiter:
    """
    Production-grade Redis-backed sliding window rate limiter.
    Executes atomic Lua script to prevent concurrency race conditions across API processes.
    Provides explicit fail-closed or fail-open policies on Redis outages.
    """
    def __init__(
        self,
        default_limit: int,
        window_seconds: int = 60,
        action_name: str = "request",
        redis_client: Optional[Any] = None
    ):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.action_name = action_name
        self._redis = redis_client
        self._script = None
        self._in_memory = SlidingWindowLimiter(max_requests=default_limit, window_seconds=window_seconds)

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        if not settings.REDIS_URL:
            return None
        try:
            import redis
            self._redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            return self._redis
        except Exception as e:
            logger.error(f"Failed to connect to Redis at {settings.REDIS_URL}: {e}")
            return None

    def check(
        self,
        key: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
        fail_closed: bool = True
    ) -> Tuple[bool, int, int]:
        """
        Atomically checks rate limit for key.
        Returns: (allowed: bool, remaining: int, retry_after: int)
        """
        # Test environment bypass unless specifically testing rate limiter
        if settings.ENVIRONMENT.lower() == "test" and not getattr(settings, "ENABLE_RATE_LIMITER_IN_TEST", False):
            return True, (limit or self.default_limit), 0

        max_req = limit or self.default_limit
        win_sec = window or self.window_seconds
        r = self._get_redis()

        if r is not None:
            try:
                now = time.time()
                member = f"{now}:{uuid.uuid4().hex[:8]}"
                res = r.eval(LUA_SLIDING_WINDOW, 1, key, now, win_sec, max_req, member)
                allowed = (res[0] == 1)
                remaining = int(res[1])
                retry_after = int(res[2])
                return allowed, remaining, retry_after
            except Exception as e:
                logger.error(f"Redis rate limiter failed for key '{key}': {e}")
                if fail_closed and getattr(settings, "FAIL_CLOSED_ON_REDIS_ERROR", True):
                    raise RateLimiterOutageError(f"Rate limiter outage for '{self.action_name}'") from e
                logger.warning(f"SharedRateLimiter falling back to in-memory sliding window for low-risk '{key}' due to Redis outage.")

        # In-memory fallback (when Redis not configured or non-fatal fail-open)
        return self._in_memory.check(key, limit=max_req, window=win_sec)

    def check_or_raise(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
        fail_closed: bool = True
    ):
        """
        Enforces rate limiting on expensive actions.
        Raises HTTP 429 with Retry-After header if limit exceeded.
        Raises HTTP 503 if Redis is unavailable and fail-closed is active.
        """
        max_req = limit or self.default_limit
        win_sec = window or self.window_seconds
        key = f"rl:{self.action_name}:{identifier}"

        try:
            allowed, _, retry_after = self.check(
                key=key,
                limit=max_req,
                window=win_sec,
                fail_closed=fail_closed
            )
        except RateLimiterOutageError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Rate limiter service is temporarily unavailable. {self.action_name.capitalize()} request rejected to prevent service disruption."
            )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: maximum {max_req} {self.action_name}s per minute permitted. Please wait {retry_after} seconds before trying again.",
                headers={"Retry-After": str(retry_after)}
            )

    def is_allowed(self, identifier: str) -> bool:
        """Backwards-compatible boolean check."""
        try:
            key = f"rl:{self.action_name}:{identifier}"
            allowed, _, _ = self.check(key=key, fail_closed=False)
            return allowed
        except Exception:
            return True


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying per-IP request rate limiting across all API endpoints.
    Excludes public health probes, API docs, and root status checks.
    """
    def __init__(self, app, max_requests_per_minute: int = 60):
        super().__init__(app)
        self.max_requests = max_requests_per_minute
        self.limiter = SharedRateLimiter(
            default_limit=max_requests_per_minute,
            window_seconds=60,
            action_name="ip"
        )
        self.excluded_paths = {
            "/",
            "/health/ready",
            "/health/live",
            "/docs",
            "/openapi.json",
            f"{settings.API_V1_STR}/health/ready",
            f"{settings.API_V1_STR}/health/live"
        }

    async def dispatch(self, request: Request, call_next):
        if settings.ENVIRONMENT.lower() == "test" and not getattr(settings, "ENABLE_RATE_LIMITER_IN_TEST", False):
            return await call_next(request)

        path = request.url.path
        if path in self.excluded_paths or request.method == "OPTIONS":
            return await call_next(request)

        # Extract verified client IP respecting trusted proxy configuration
        client_ip = get_trusted_client_ip(request)
        key = f"rl:ip:{client_ip}"

        allowed, _, retry_after = self.limiter.check(
            key=key,
            limit=self.max_requests,
            window=60,
            fail_closed=False  # Low-risk IP browsing falls back safely without breaking site
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {client_ip} on path {path}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Too many requests. Please slow down and try again in {retry_after} seconds."
                },
                headers={"Retry-After": str(retry_after)}
            )

        return await call_next(request)


# Shared rate limiters for distinct actions
ip_rate_limiter = SharedRateLimiter(
    default_limit=settings.MAX_REQUESTS_PER_MINUTE_PER_IP,
    window_seconds=60,
    action_name="ip"
)

upload_rate_limiter = SharedRateLimiter(
    default_limit=settings.MAX_UPLOADS_PER_MINUTE_PER_USER,
    window_seconds=60,
    action_name="upload"
)

audit_rate_limiter = SharedRateLimiter(
    default_limit=settings.MAX_AUDIT_SUBMISSIONS_PER_MINUTE_PER_USER,
    window_seconds=60,
    action_name="audit"
)

rag_rate_limiter = SharedRateLimiter(
    default_limit=settings.MAX_RAG_QUERIES_PER_MINUTE_PER_USER,
    window_seconds=60,
    action_name="rag"
)


class BudgetTracker:
    """
    In-memory compatibility view of AI provider spend.
    Primary durable ledger is enforced in PostgreSQL via AIBudgetService.
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
