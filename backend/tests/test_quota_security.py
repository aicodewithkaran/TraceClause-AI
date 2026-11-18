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

def test_mock_analysis_strictly_blocked_in_production(monkeypatch):
    """Assert LLMAnalyzer raises RuntimeError rather than returning mock analysis in production."""
    from app.services.llm_analyzer import LLMAnalyzer
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_DEMO_AUTH", False)

    analyzer = LLMAnalyzer()
    analyzer.provider = "mock"

    with pytest.raises(RuntimeError) as exc_info:
        analyzer._analyze_batch([{"clause_number": 1, "clause_name": "Test Clause", "text": "This is test text"}])
    assert "Mock legal analysis is strictly prohibited in production" in str(exc_info.value)

def test_synchronous_analysis_blocked_in_production(client, monkeypatch):
    """Assert synchronous POST /api/v1/contract/analyze returns 403 Forbidden in production to enforce queue."""
    from app.core.config import settings
    from app.core.security import AuthenticatedUser, get_current_user
    from app.main import app

    mock_user = AuthenticatedUser(id="user-prod-123", email="user@example.com")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_SYNCHRONOUS_ANALYSIS", False)

    try:
        payload = {
            "file_name": "contract.pdf",
            "extracted_text": "Sample text for contract analysis"
        }
        res = client.post("/api/v1/contract/analyze", json=payload, headers={"Authorization": "Bearer some-token"})
        assert res.status_code == 403
        assert "synchronous analysis is disabled" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_ai_budget_limit_circuit_breaker_trips(monkeypatch):
    """Assert LLMAnalyzer trips circuit breaker and stops execution when monthly budget limit is exceeded."""
    from app.services.llm_analyzer import LLMAnalyzer
    from app.core.rate_limiter import budget_tracker

    # Reset budget tracker state for test
    original_spend = budget_tracker.estimated_spend_usd
    original_limit = budget_tracker.monthly_budget_usd

    try:
        budget_tracker.monthly_budget_usd = 5.0
        budget_tracker.estimated_spend_usd = 0.0

        # Record usage below limit
        budget_tracker.record_usage(2.5)
        assert budget_tracker.is_budget_exceeded() is False
        assert budget_tracker.estimated_spend_usd == 2.5

        # Exceed budget limit
        budget_tracker.record_usage(3.0)  # Total 5.5 > 5.0
        assert budget_tracker.is_budget_exceeded() is True

        analyzer = LLMAnalyzer()
        with pytest.raises(RuntimeError) as exc_info:
            analyzer._analyze_batch([{"clause_number": 1, "clause_name": "Test", "text": "Sample text"}])
        assert "Monthly AI budget hard limit" in str(exc_info.value)
    finally:
        budget_tracker.estimated_spend_usd = original_spend
        budget_tracker.monthly_budget_usd = original_limit

def test_malformed_model_output_fails_closed_instead_of_defaulting_to_low():
    """Assert _parse_batch_json strictly raises on missing or omitted clauses rather than masking with 'Low' risk."""
    from app.services.llm_analyzer import LLMAnalyzer
    analyzer = LLMAnalyzer()

    batch = [
        {"clause_number": 1, "clause_name": "Indemnity", "text": "Customer shall indemnify Vendor."},
        {"clause_number": 2, "clause_name": "Termination", "text": "May terminate on 30 days notice."}
    ]

    # Scenario 1: Model returned only clause 1, dropping clause 2
    partial_model_output = [
        {"clause_number": 1, "clause_name": "Indemnity", "risk_level": "High", "risk_explanation": "Uncapped liability"}
    ]
    with pytest.raises(RuntimeError) as exc_info1:
        analyzer._parse_batch_json(batch, partial_model_output)
    assert "was omitted from the model output" in str(exc_info1.value)

    # Scenario 2: Model returned unrecognized or invalid risk_level
    invalid_risk_output = [
        {"clause_number": 1, "clause_name": "Indemnity", "risk_level": "UNKNOWN", "risk_explanation": "..."},
        {"clause_number": 2, "clause_name": "Termination", "risk_level": "Low", "risk_explanation": "..."}
    ]
    with pytest.raises(RuntimeError) as exc_info2:
        analyzer._parse_batch_json(batch, invalid_risk_output)
    assert "unrecognized risk level 'UNKNOWN'" in str(exc_info2.value)

    # Scenario 3: Valid complete output succeeds with capitalized risk levels
    valid_output = [
        {"clause_number": 1, "clause_name": "Indemnity", "risk_level": "high", "risk_explanation": "Broad indemnity"},
        {"clause_number": 2, "clause_name": "Termination", "risk_level": "low", "risk_explanation": "Standard 30 days"}
    ]
    results = analyzer._parse_batch_json(batch, valid_output)
    assert len(results) == 2
    assert results[0].risk_level == "High"
    assert results[1].risk_level == "Low"




