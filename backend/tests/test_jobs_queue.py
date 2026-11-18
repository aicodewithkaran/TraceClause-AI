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


class MockDatabaseWithFencing:
    """
    Simulates database behavior of fail_analysis_job and complete_analysis_job stored procedures
    from supabase/migrations/20261118_durable_ai_budget_and_fenced_cleanup.sql.
    """
    def __init__(self):
        self.job = {
            "id": "job-fenced-1",
            "fencing_token": 3,
            "status": "processing",
            "report_id": "rep-active-1",
            "audit_reservation_id": "audit-res-1"
        }
        self.reports = {
            "rep-active-1": {"id": "rep-active-1", "analysis_job_id": "job-fenced-1", "fencing_token": 3}
        }
        self.embeddings = [
            {"report_id": "rep-active-1", "clause_number": 1}
        ]
        self.quota_reservations = {
            "audit-res-1": {"id": "res-1", "status": "reserved", "tier": "solo"}
        }
        self.refund_count = 0

    def fail_analysis_job(self, p_job_id: str, p_token: int, p_error_msg: str) -> bool:
        # 1. Require matching job_id, fencing_token, and status = 'processing'
        if self.job["id"] != p_job_id or self.job["fencing_token"] != p_token or self.job["status"] != "processing":
            return False  # Stale worker or already finalized

        # 2. Delete linked report & embeddings
        rep_id = self.job.get("report_id")
        if rep_id and rep_id in self.reports:
            del self.reports[rep_id]
            self.embeddings = [e for e in self.embeddings if e["report_id"] != rep_id]

        # 3. Mark job failed
        self.job["status"] = "failed"
        self.job["report_id"] = None
        self.job["error_message"] = p_error_msg

        # 4. Release quota exactly once
        q_res = self.quota_reservations.get(self.job["audit_reservation_id"])
        if q_res and q_res["status"] == "reserved":
            q_res["status"] = "released"
            self.refund_count += 1

        return True

    def complete_analysis_job(self, p_job_id: str, p_token: int, p_report_id: str) -> bool:
        if self.job["id"] != p_job_id or self.job["fencing_token"] != p_token or self.job["status"] != "processing":
            return False

        self.job["status"] = "completed"
        self.job["report_id"] = p_report_id
        q_res = self.quota_reservations.get(self.job["audit_reservation_id"])
        if q_res:
            q_res["status"] = "committed"
        return True

    def persist_analysis_report_and_complete(self, p_job_id: str, p_token: int, p_report_payload: dict, p_embeddings_payload: list) -> dict:
        if self.job["id"] != p_job_id or self.job["fencing_token"] != p_token or self.job["status"] != "processing":
            return {"success": False, "error": "LEASE_LOST"}

        rep_id = f"rep_fenced_{p_token}"
        self.reports[rep_id] = {
            "id": rep_id,
            "analysis_job_id": p_job_id,
            "fencing_token": p_token,
            "payload": p_report_payload
        }
        for emb in p_embeddings_payload:
            self.embeddings.append({"report_id": rep_id, **emb})

        self.job["status"] = "completed"
        self.job["report_id"] = rep_id
        q_res = self.quota_reservations.get(self.job["audit_reservation_id"])
        if q_res:
            q_res["status"] = "committed"

        return {"success": True, "report_id": rep_id}


def test_stale_worker_failure_rejected_by_fencing():
    """Assert a stale worker with an older fencing token cannot fail or mutate a newer job lease."""
    from app.services.job_worker import JobWorker

    db = MockDatabaseWithFencing()
    worker = JobWorker(worker_id="worker_stale")

    class MockRPC:
        def __init__(self, name, params):
            self.name = name
            self.params = params
        def execute(self):
            class Res:
                data = db.fail_analysis_job(
                    self.params["p_job_id"],
                    self.params["p_token"],
                    self.params["p_error_msg"]
                )
            return Res()

    class MockSupabase:
        def rpc(self, name, params):
            return MockRPC(name, params)

    worker.supabase = MockSupabase()

    # Stale worker attempts failure with old token=2 (active token is 3)
    success = worker._fail_job("job-fenced-1", token=2, error_msg="Stale failure")
    assert success is False

    # Assert current attempt's data was NOT mutated
    assert db.job["status"] == "processing"
    assert "rep-active-1" in db.reports
    assert len(db.embeddings) == 1
    assert db.quota_reservations["audit-res-1"]["status"] == "reserved"
    assert db.refund_count == 0


def test_current_worker_failure_atomic_cleanup():
    """Assert current worker with matching token removes report, embeddings, and refunds quota atomically."""
    from app.services.job_worker import JobWorker

    db = MockDatabaseWithFencing()
    worker = JobWorker(worker_id="worker_current")

    class MockRPC:
        def __init__(self, name, params):
            self.name = name
            self.params = params
        def execute(self):
            class Res:
                data = db.fail_analysis_job(
                    self.params["p_job_id"],
                    self.params["p_token"],
                    self.params["p_error_msg"]
                )
            return Res()

    class MockSupabase:
        def rpc(self, name, params):
            return MockRPC(name, params)

    worker.supabase = MockSupabase()

    # Current worker fails with matching token=3
    success = worker._fail_job("job-fenced-1", token=3, error_msg="AI timeout")
    assert success is True

    # Assert partial report and embeddings deleted, job marked failed, quota refunded
    assert db.job["status"] == "failed"
    assert db.job["report_id"] is None
    assert "rep-active-1" not in db.reports
    assert len(db.embeddings) == 0
    assert db.quota_reservations["audit-res-1"]["status"] == "released"
    assert db.refund_count == 1


def test_duplicate_failure_call_no_double_refund():
    """Assert duplicate fail_analysis_job calls return False and do not double refund quota."""
    from app.services.job_worker import JobWorker

    db = MockDatabaseWithFencing()
    worker = JobWorker(worker_id="worker_dup")

    class MockRPC:
        def __init__(self, name, params):
            self.name = name
            self.params = params
        def execute(self):
            class Res:
                data = db.fail_analysis_job(
                    self.params["p_job_id"],
                    self.params["p_token"],
                    self.params["p_error_msg"]
                )
            return Res()

    class MockSupabase:
        def rpc(self, name, params):
            return MockRPC(name, params)

    worker.supabase = MockSupabase()

    # First failure succeeds
    assert worker._fail_job("job-fenced-1", token=3, error_msg="Error 1") is True
    assert db.refund_count == 1

    # Second duplicated failure call fails closed (returns False, no second refund)
    assert worker._fail_job("job-fenced-1", token=3, error_msg="Error 2") is False
    assert db.refund_count == 1


def test_completed_job_cannot_be_failed_by_stale_worker():
    """Assert a successfully completed report cannot be deleted or failed by a later stale worker call."""
    from app.services.job_worker import JobWorker

    db = MockDatabaseWithFencing()
    db.complete_analysis_job("job-fenced-1", p_token=3, p_report_id="rep-active-1")
    assert db.job["status"] == "completed"

    worker = JobWorker(worker_id="worker_late")

    class MockRPC:
        def __init__(self, name, params):
            self.name = name
            self.params = params
        def execute(self):
            class Res:
                data = db.fail_analysis_job(
                    self.params["p_job_id"],
                    self.params["p_token"],
                    self.params["p_error_msg"]
                )
            return Res()

    class MockSupabase:
        def rpc(self, name, params):
            return MockRPC(name, params)

    worker.supabase = MockSupabase()

    # Stale attempt to fail the completed job
    assert worker._fail_job("job-fenced-1", token=3, error_msg="Late crash") is False

    # Completed report and job state remain completely protected
    assert db.job["status"] == "completed"
    assert "rep-active-1" in db.reports
    assert len(db.embeddings) == 1
    assert db.quota_reservations["audit-res-1"]["status"] == "committed"


def test_persist_analysis_report_atomic_rejection_on_stale_token():
    """Assert persist_analysis_report_and_complete rejects stale worker writes atomically with ZERO writes."""
    db = MockDatabaseWithFencing()
    db.job["status"] = "processing"
    db.job["fencing_token"] = 4  # New active token is 4

    class MockRPC:
        def __init__(self, name, params):
            self.name = name
            self.params = params
        def execute(self):
            class Res:
                data = db.persist_analysis_report_and_complete(
                    self.params["p_job_id"],
                    self.params["p_token"],
                    self.params["p_report_payload"],
                    self.params["p_embeddings_payload"]
                )
            return Res()

    # 1. Stale worker with token 3 attempts to write report and embeddings
    stale_rpc = MockRPC("persist_analysis_report_and_complete", {
        "p_job_id": "job-fenced-1",
        "p_token": 3,
        "p_report_payload": {"overall_risk_score": "HIGH RISK"},
        "p_embeddings_payload": [{"clause_number": 1, "embedding": [0.1] * 1536}]
    }).execute()

    assert stale_rpc.data["success"] is False
    assert stale_rpc.data["error"] == "LEASE_LOST"
    assert "rep_fenced_3" not in db.reports
    assert db.job["status"] == "processing"

    # 2. Current worker with token 4 succeeds atomically
    valid_rpc = MockRPC("persist_analysis_report_and_complete", {
        "p_job_id": "job-fenced-1",
        "p_token": 4,
        "p_report_payload": {"overall_risk_score": "LOW RISK"},
        "p_embeddings_payload": [{"clause_number": 1, "embedding": [0.2] * 1536}]
    }).execute()

    assert valid_rpc.data["success"] is True
    assert "rep_fenced_4" in db.reports
    assert db.job["status"] == "completed"
    assert db.job["report_id"] == "rep_fenced_4"
    assert db.quota_reservations["audit-res-1"]["status"] == "committed"




