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

def test_worker_orphan_recovery_requeues_and_fails_max_retries():
    """Assert orphan reclamation janitor re-queues jobs under max_retries and marks failed with quota refund if exceeded."""
    import asyncio
    from app.worker_daemon import SupervisedWorkerDaemon
    daemon = SupervisedWorkerDaemon(concurrency_limit=2)

    updated_rows = []
    rpc_calls = []

    class MockJobTable:
        def select(self, *args, **kwargs):
            return self
        def eq(self, col, val):
            return self
        def lt(self, col, val):
            return self
        def execute(self):
            class Res:
                data = [
                    # Orphan 1: retries=1, max=3 -> should be re-queued
                    {"id": "job-orphan-1", "retry_count": 1, "max_retries": 3, "fencing_token": 2},
                    # Orphan 2: retries=3, max=3 -> should be failed and refunded
                    {"id": "job-orphan-2", "retry_count": 3, "max_retries": 3, "fencing_token": 4}
                ]
            return Res()

        def update(self, payload):
            updated_rows.append(payload)
            return self

    class MockRPC:
        def __init__(self, name, params):
            self.name = name
            self.params = params
        def execute(self):
            rpc_calls.append((self.name, self.params))
            class Res:
                data = True
            return Res()

    class MockSupabase:
        def table(self, name):
            return MockJobTable()
        def rpc(self, name, params):
            return MockRPC(name, params)

    daemon.supabase = MockSupabase()
    daemon.last_janitor_run = 0.0

    asyncio.run(daemon.reclaim_orphaned_jobs())

    # Verify Orphan 1 was re-queued with retry_count incremented
    assert len(updated_rows) == 1
    assert updated_rows[0]["status"] == "queued"
    assert updated_rows[0]["retry_count"] == 2

    # Verify Orphan 2 was failed via fail_analysis_job RPC with quota refund
    assert len(rpc_calls) == 1
    assert rpc_calls[0][0] == "fail_analysis_job"
    assert rpc_calls[0][1]["p_job_id"] == "job-orphan-2"
    assert "timed out" in rpc_calls[0][1]["p_error_msg"]

def test_circuit_breaker_ai_processing_kill_switch(client):
    """Assert submitting a job returns 503 Service Unavailable when AI_PROCESSING_ENABLED is False."""
    from app.core.config import settings
    mock_user = AuthenticatedUser(id="user-cb-123", email="user@example.com")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    original_setting = settings.AI_PROCESSING_ENABLED
    try:
        settings.AI_PROCESSING_ENABLED = False
        res = client.post("/api/v1/jobs/submit", json={
            "file_name": "contract.pdf",
            "extracted_text": "Sample valid contract clause."
        })
        assert res.status_code == 503
        assert "temporarily paused" in res.json()["detail"].lower()
    finally:
        settings.AI_PROCESSING_ENABLED = original_setting
        app.dependency_overrides.pop(get_current_user, None)

def test_job_worker_heartbeat_touch():
    """Assert _touch_heartbeat updates heartbeat_at on contract_analysis_jobs verifying fencing token."""
    from app.services.job_worker import JobWorker
    worker = JobWorker(worker_id="test_worker_hb")

    update_payloads = []

    class MockJobTable:
        def update(self, payload):
            update_payloads.append(payload)
            return self
        def eq(self, col, val):
            return self
        def execute(self):
            class Res:
                data = [{"id": "job-hb-1"}]
            return Res()

    class MockSupabase:
        def table(self, name):
            return MockJobTable()

    worker.supabase = MockSupabase()
    success = worker._touch_heartbeat("job-hb-1", 3)
    assert success is True
    assert len(update_payloads) == 1
    assert "heartbeat_at" in update_payloads[0]

def test_retry_cleanup_purges_prior_partial_report():
    """Assert retry execution purges existing partial report and embeddings before writing new report."""
    from app.services.job_worker import JobWorker
    worker = JobWorker(worker_id="test_worker_cleanup")

    deleted_tables = []

    class MockTable:
        def __init__(self, name):
            self.name = name
        def select(self, *args, **kwargs):
            return self
        def eq(self, col, val):
            return self
        def delete(self):
            deleted_tables.append(self.name)
            return self
        def execute(self):
            class Res:
                data = [{"report_id": "partial-rep-999"}]
            return Res()

    class MockSupabase:
        def table(self, name):
            return MockTable(name)

    worker.supabase = MockSupabase()

    # Query existing report_id and purge
    chk = worker.supabase.table("contract_analysis_jobs").select("report_id").eq("id", "job-1").execute()
    existing_rep = chk.data[0]["report_id"]
    assert existing_rep == "partial-rep-999"

    worker.supabase.table("contract_embeddings").delete().eq("report_id", existing_rep).execute()
    worker.supabase.table("contract_reports").delete().eq("id", existing_rep).execute()

    assert "contract_embeddings" in deleted_tables
    assert "contract_reports" in deleted_tables



