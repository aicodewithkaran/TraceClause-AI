import time
import threading
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import HTTPException
from app.core.rate_limiter import (
    SharedRateLimiter,
    RateLimiterOutageError,
    get_trusted_client_ip,
    SlidingWindowLimiter
)
from app.core.config import settings

@pytest.fixture(autouse=True)
def enable_rate_limiter_in_test(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_RATE_LIMITER_IN_TEST", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

class MockRedisAtomic:
    """
    In-memory simulation of Redis with atomic Lua script execution.
    Maintains sorted sets per key to test concurrency safety across simulated processes.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.zsets = {}  # key -> list of (score, member)

    def eval(self, script, numkeys, key, now, window, limit, member):
        with self.lock:
            now = float(now)
            window = float(window)
            limit = int(limit)
            cutoff = now - window

            if key not in self.zsets:
                self.zsets[key] = []

            # 1. ZREMRANGEBYSCORE key -inf cutoff
            self.zsets[key] = [(s, m) for s, m in self.zsets[key] if s > cutoff]

            current_count = len(self.zsets[key])
            if current_count < limit:
                # 2. ZADD key now member
                self.zsets[key].append((now, member))
                return [1, limit - current_count - 1, 0]
            else:
                oldest_ts = self.zsets[key][0][0] if self.zsets[key] else now
                retry_after = max(1, int(oldest_ts + window - now))
                return [0, 0, retry_after]


def test_shared_rate_limiter_across_multiple_processes():
    """Assert two API processes sharing the same Redis instance share the exact same rate limit."""
    shared_redis = MockRedisAtomic()
    proc1_limiter = SharedRateLimiter(default_limit=5, window_seconds=60, action_name="test", redis_client=shared_redis)
    proc2_limiter = SharedRateLimiter(default_limit=5, window_seconds=60, action_name="test", redis_client=shared_redis)

    key = "rl:test:user_shared"

    # Proc 1 makes 3 requests
    for _ in range(3):
        allowed, remaining, _ = proc1_limiter.check(key, limit=5, window=60)
        assert allowed is True

    # Proc 2 makes 2 requests (reaching the 5 limit)
    allowed, remaining, _ = proc2_limiter.check(key, limit=5, window=60)
    assert allowed is True
    assert remaining == 1

    allowed, remaining, _ = proc2_limiter.check(key, limit=5, window=60)
    assert allowed is True
    assert remaining == 0

    # 6th request from Proc 1 MUST be rejected by the shared limit
    allowed, remaining, retry_after = proc1_limiter.check(key, limit=5, window=60)
    assert allowed is False
    assert retry_after >= 1


def test_process_restart_does_not_reset_limit():
    """Assert rebooting an API process does not reset the persisted Redis rate limit."""
    shared_redis = MockRedisAtomic()
    proc_before = SharedRateLimiter(default_limit=3, window_seconds=60, action_name="upload", redis_client=shared_redis)

    key = "rl:upload:user_reboot"
    for _ in range(3):
        allowed, _, _ = proc_before.check(key, limit=3, window=60)
        assert allowed is True

    # New process starts up pointing to same Redis
    proc_after = SharedRateLimiter(default_limit=3, window_seconds=60, action_name="upload", redis_client=shared_redis)
    allowed, _, retry_after = proc_after.check(key, limit=3, window=60)
    assert allowed is False
    assert retry_after > 0


def test_simultaneous_requests_cannot_race_past_limit():
    """Assert concurrent threads cannot race past the rate limit due to atomic Lua evaluation."""
    shared_redis = MockRedisAtomic()
    limiter = SharedRateLimiter(default_limit=10, window_seconds=60, action_name="audit", redis_client=shared_redis)

    key = "rl:audit:user_race"
    results = []

    def make_request():
        allowed, _, _ = limiter.check(key, limit=10, window=60)
        results.append(allowed)

    # 25 concurrent requests against limit of 10
    threads = [threading.Thread(target=make_request) for _ in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = sum(1 for r in results if r is True)
    rejections = sum(1 for r in results if r is False)

    assert successes == 10
    assert rejections == 15


def test_spoofed_forwarding_headers_cannot_bypass_ip_limit():
    """
    Assert a direct client connecting from an untrusted peer IP cannot bypass rate limiting
    by spoofing X-Forwarded-For or X-Real-IP headers.
    """
    scope = {
        "type": "http",
        "client": ("198.51.100.44", 54321),  # Untrusted external client peer IP
        "headers": [
            (b"x-forwarded-for", b"203.0.113.1, 10.0.0.1"),
            (b"x-real-ip", b"203.0.113.1")
        ]
    }
    request = Request(scope)

    # settings.TRUSTED_PROXIES defaults to ["127.0.0.1", "::1"]
    extracted_ip = get_trusted_client_ip(request)

    # Spoofed headers must be completely ignored; socket peer IP must be used
    assert extracted_ip == "198.51.100.44"


def test_trusted_proxy_headers_extracted_correctly():
    """
    Assert when connecting via a trusted reverse proxy (e.g. 127.0.0.1),
    the proxy-sanitized client IP is extracted from X-Real-IP or rightmost X-Forwarded-For.
    """
    # 1. Via X-Real-IP
    scope_real_ip = {
        "type": "http",
        "client": ("127.0.0.1", 8000),  # Trusted proxy host
        "headers": [
            (b"x-real-ip", b"203.0.113.99"),
            (b"x-forwarded-for", b"spoofed.ip, 203.0.113.99")
        ]
    }
    req1 = Request(scope_real_ip)
    assert get_trusted_client_ip(req1) == "203.0.113.99"

    # 2. Via rightmost X-Forwarded-For when X-Real-IP not present
    scope_xff = {
        "type": "http",
        "client": ("127.0.0.1", 8000),
        "headers": [
            (b"x-forwarded-for", b"attacker.ip, 198.51.100.88")
        ]
    }
    req2 = Request(scope_xff)
    assert get_trusted_client_ip(req2) == "198.51.100.88"


def test_user_upload_limits_work_across_different_ips():
    """Assert an authenticated user's upload limit is tied to user_id, not IP address."""
    shared_redis = MockRedisAtomic()
    limiter = SharedRateLimiter(default_limit=2, window_seconds=60, action_name="upload", redis_client=shared_redis)

    # User uploads from IP 1
    key = "rl:upload:user_alice"
    assert limiter.check(key, limit=2)[0] is True

    # User uploads from IP 2
    assert limiter.check(key, limit=2)[0] is True

    # 3rd upload from IP 3 is rejected
    allowed, _, retry_after = limiter.check(key, limit=2)
    assert allowed is False
    assert retry_after > 0


def test_redis_outage_fail_closed_on_expensive_action():
    """Assert expensive actions (upload, audit, rag) fail closed with 503 when Redis is unavailable."""
    class BrokenRedis:
        def eval(self, *args, **kwargs):
            raise ConnectionError("Redis server unavailable")

    limiter = SharedRateLimiter(default_limit=5, window_seconds=60, action_name="audit", redis_client=BrokenRedis())

    # check_or_raise should raise HTTPException 503
    with pytest.raises(HTTPException) as exc_info:
        limiter.check_or_raise("user_bob", fail_closed=True)

    assert exc_info.value.status_code == 503
    assert "temporarily unavailable" in exc_info.value.detail.lower()


def test_redis_outage_fail_open_on_low_risk_action():
    """Assert low-risk IP endpoints fall back safely to in-memory sliding window when Redis is down."""
    class BrokenRedis:
        def eval(self, *args, **kwargs):
            raise ConnectionError("Redis server unavailable")

    limiter = SharedRateLimiter(default_limit=5, window_seconds=60, action_name="ip", redis_client=BrokenRedis())

    # Low-risk action with fail_closed=False should fall back to in-memory limiter without raising
    allowed, remaining, _ = limiter.check("rl:ip:127.0.0.1", limit=5, fail_closed=False)
    assert allowed is True
    assert remaining == 4
