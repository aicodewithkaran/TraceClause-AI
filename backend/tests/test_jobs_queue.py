import pytest
from app.core.security import AuthenticatedUser, get_current_user
from app.main import app

def test_job_submit_requires_auth(client):
    """Assert submitting a contract analysis job requires authentication."""
    res = client.post("/api/v1/jobs/submit", json={
        "file_name": "test_contract.pdf",
        "extracted_text": "Sample contract clause text"
    })
    assert res.status_code == 401

def test_job_submit_empty_text_rejected(client):
    """Assert submitting job with empty text is rejected with 400."""
    mock_user = AuthenticatedUser(id="user-job-123", email="user@example.com")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        res = client.post("/api/v1/jobs/submit", json={
            "file_name": "empty.pdf",
            "extracted_text": "   "
        })
        assert res.status_code == 400
        assert "cannot be empty" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_health_liveness_probe(client):
    """Assert /health/live returns 200 alive without touching database."""
    res = client.get("/api/v1/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "alive"
    assert "version" in data

def test_health_readiness_probe_healthy(client, monkeypatch):
    """Assert /health/ready returns 200 healthy when database ping succeeds."""
    from app.api.v1.endpoints import health as health_module
    
    class MockTable:
        count = 0
        def select(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self
        def in_(self, *args, **kwargs):
            return self
        def execute(self):
            class Res:
                data = [{"id": 1}]
                count = 0
            return Res()

    class MockSupabase:
        def table(self, name):
            return MockTable()

    monkeypatch.setattr(health_module, "_get_supabase_client", lambda: MockSupabase())

    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"

def test_health_readiness_probe_unhealthy(client, monkeypatch):
    """Assert /health/ready returns 503 degraded when database connectivity fails."""
    from app.api.v1.endpoints import health as health_module

    class BrokenSupabase:
        def table(self, name):
            raise ConnectionError("Supabase unreachable")

    monkeypatch.setattr(health_module, "_get_supabase_client", lambda: BrokenSupabase())

    res = client.get("/api/v1/health/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "unhealthy"
    assert data["database"] == "connection_failed"

def test_worker_fencing_token_mismatch_prevents_completion():
    """Assert worker fails closed and refuses to commit job if fencing token is mismatched."""
    from app.services.job_worker import JobWorker

    worker = JobWorker(worker_id="test_worker_alpha")

    class MockRPC:
        def __init__(self, fn_name, params):
            self.fn_name = fn_name
            self.params = params

        def execute(self):
            class Res:
                # If token matches active token (say 2), succeed; if token is stale (1), fail
                data = True if self.params.get("p_token") == 2 else False
            return Res()

    class MockSupabase:
        def rpc(self, name, params):
            return MockRPC(name, params)

    worker.supabase = MockSupabase()

    # Active token 2 -> succeeds
    assert worker._complete_job("job-123", 2, "rep-456") is True

    # Stale / expired token 1 -> rejected, returns False
    assert worker._complete_job("job-123", 1, "rep-456") is False
    assert worker._fail_job("job-123", 1, "stale error") is False

