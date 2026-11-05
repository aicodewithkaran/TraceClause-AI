import pytest
from fastapi import HTTPException
from app.services.quota_service import QuotaService
from app.api.v1.endpoints.analysis import analyze_contract
from app.core.security import AuthenticatedUser

def test_quota_service_fails_closed_when_db_unavailable(monkeypatch):
    """Assert QuotaService fails closed with 503 instead of returning free quota when DB unavailable."""
    monkeypatch.setattr(QuotaService, "get_supabase_client", lambda: None)
    with pytest.raises(HTTPException) as exc_info:
        QuotaService.reserve_quota("user-123", "audit-456")
    assert exc_info.value.status_code == 503
    assert "Database service unavailable" in exc_info.value.detail

def test_quota_service_raises_429_on_quota_exceeded(monkeypatch):
    """Assert QuotaService maps QUOTA_EXCEEDED database error to HTTP 429."""
    class MockClient:
        def rpc(self, func_name, params):
            class MockCall:
                def execute(self):
                    raise Exception("QUOTA_EXCEEDED: Free trial limit reached (3/3 contracts)")
            return MockCall()

    monkeypatch.setattr(QuotaService, "get_supabase_client", lambda: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        QuotaService.reserve_quota("user-123", "audit-456")
    assert exc_info.value.status_code == 429
    assert "Contract audit limit reached" in exc_info.value.detail

def test_analysis_releases_quota_reservation_on_failure(client, monkeypatch, user_a):
    """Assert quota is released via compensating rollback if analysis throws an unexpected exception."""
    released_reservations = []
    committed_reservations = []

    monkeypatch.setattr(QuotaService, "reserve_quota", lambda uid, aid: {"quota_used": 1, "limit": 3, "tier": "free", "remaining": 2})
    monkeypatch.setattr(QuotaService, "release_quota", lambda uid, aid: released_reservations.append((uid, aid)))
    monkeypatch.setattr(QuotaService, "commit_quota", lambda uid, aid: committed_reservations.append((uid, aid)))

    # Force ChunkingEngine to raise an error
    from app.services.chunking import ChunkingEngine
    monkeypatch.setattr(ChunkingEngine, "split_into_clauses", lambda text: (_ for _ in ()).throw(ValueError("Simulated parsing crash")))

    from app.core.security import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: user_a

    try:
        payload = {
            "file_name": "contract.pdf",
            "extracted_text": "Sample text for contract analysis"
        }
        res = client.post("/api/v1/contract/analyze", json=payload, headers={"Authorization": "Bearer dev-token"})
        assert res.status_code == 500
        # Verify compensating release was triggered
        assert len(released_reservations) == 1
        assert released_reservations[0][0] == user_a.id
        assert len(committed_reservations) == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)

