import pytest
from app.core.config import Settings, settings
from app.services.user_isolation import UserIsolationService
from app.core.security import get_current_user, AuthenticatedUser
from app.main import app

def test_protected_routes_require_authentication(client):
    """Verify that every protected route fails closed with 401 when no auth header is present."""
    routes_to_test = [
        ("POST", "/api/v1/documents/upload", {}),
        ("POST", "/api/v1/contract/analyze", {"json": {"file_name": "test.pdf", "extracted_text": "sample text"}}),
        ("GET", "/api/v1/contract/my-reports", {}),
        ("GET", "/api/v1/contract/test-report-id/export-docx", {}),
        ("DELETE", "/api/v1/contract/test-report-id", {}),
        ("GET", "/api/v1/workspaces/", {}),
        ("POST", "/api/v1/workspaces/", {"json": {"name": "Test Workspace"}}),
        ("POST", "/api/v1/rag/chat", {"json": {"contract_text": "sample", "question": "test?"}}),
        ("POST", "/api/v1/payments/razorpay/create-order", {"json": {"plan_tier": "solo"}}),
    ]

    for method, path, kwargs in routes_to_test:
        if method == "POST":
            res = client.post(path, **kwargs)
        elif method == "GET":
            res = client.get(path, **kwargs)
        elif method == "DELETE":
            res = client.delete(path, **kwargs)
        
        assert res.status_code == 401, f"Route {method} {path} did not return 401, got {res.status_code}"

def test_demo_auth_blocked_when_disabled(client, monkeypatch):
    """Assert demo tokens return 401 when ALLOW_DEMO_AUTH is False."""
    monkeypatch.setattr(settings, "ALLOW_DEMO_AUTH", False)
    res = client.get("/api/v1/contract/my-reports", headers={"Authorization": "Bearer dev-token"})
    assert res.status_code == 401
    assert "Demo tokens are disabled" in res.json()["detail"]

def test_production_startup_validation_blocks_demo_auth():
    """Assert production environment refuses to start if ALLOW_DEMO_AUTH is True."""
    bad_settings = Settings(
        ENVIRONMENT="production",
        ALLOW_DEMO_AUTH=True,
        SECRET_KEY="a" * 32,
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_KEY="test_anon_key",
        SUPABASE_SERVICE_ROLE_KEY="test_service_key",
        OPENAI_API_KEY="test_openai_key"
    )
    with pytest.raises(RuntimeError) as exc_info:
        bad_settings.validate_security_configuration()
    assert "ALLOW_DEMO_AUTH cannot be True in production" in str(exc_info.value)

def test_production_startup_validation_blocks_weak_secret():
    """Assert production environment refuses to start with weak or default SECRET_KEY."""
    bad_settings = Settings(
        ENVIRONMENT="production",
        ALLOW_DEMO_AUTH=False,
        SECRET_KEY="supersecretkey",  # known weak default
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_KEY="test_anon_key",
        SUPABASE_SERVICE_ROLE_KEY="test_service_key",
        OPENAI_API_KEY="test_openai_key"
    )
    with pytest.raises(RuntimeError) as exc_info:
        bad_settings.validate_security_configuration()
    assert "SECRET_KEY must be a cryptographically secure key" in str(exc_info.value)

def test_cross_tenant_isolation_report_export(client, monkeypatch, user_a, user_b):
    """Assert User B cannot access or export User A's private contract report."""
    # Mock UserIsolationService.get_user_report_by_id to enforce isolation logic
    def mock_get_report(caller_user_id, report_id):
        # Report belongs to User A
        if caller_user_id == user_a.id:
            return {"id": report_id, "user_id": user_a.id, "file_name": "user_a_nda.pdf"}
        # Caller is User B -> access denied
        return None

    monkeypatch.setattr(UserIsolationService, "get_user_report_by_id", mock_get_report)

    # Act as User B with solo subscription tier
    from app.core.dependencies import get_current_profile
    app.dependency_overrides[get_current_user] = lambda: user_b
    app.dependency_overrides[get_current_profile] = lambda: {"id": user_b.id, "subscription_tier": "solo", "auth_user": user_b}
    try:
        res = client.get("/api/v1/contract/report-12345/export-docx", headers={"Authorization": "Bearer valid-b-token"})
        assert res.status_code == 404
        assert "not found or access denied" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_profile, None)

def test_cross_tenant_isolation_report_delete(client, monkeypatch, user_a, user_b):
    """Assert User B cannot delete User A's private contract report."""
    def mock_delete_report(caller_user_id, report_id):
        if caller_user_id == user_a.id:
            return True
        return False

    monkeypatch.setattr(UserIsolationService, "delete_user_report", mock_delete_report)

    # Act as User B attempting to delete User A's report
    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        res = client.delete("/api/v1/contract/report-12345", headers={"Authorization": "Bearer valid-b-token"})
        assert res.status_code == 404
        assert "deletion access denied" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_cross_tenant_isolation_rag_chat(client, monkeypatch, user_a, user_b):
    """Assert User B cannot query User A's contract via RAG chat."""
    def mock_get_report(caller_user_id, report_id):
        if caller_user_id == user_a.id:
            return {"id": report_id, "user_id": user_a.id}
        return None

    monkeypatch.setattr(UserIsolationService, "get_user_report_by_id", mock_get_report)

    # Act as User B with solo subscription tier
    from app.core.dependencies import get_current_profile
    app.dependency_overrides[get_current_user] = lambda: user_b
    app.dependency_overrides[get_current_profile] = lambda: {"id": user_b.id, "subscription_tier": "solo", "auth_user": user_b}
    try:
        payload = {
            "contract_id": "contract-user-a-secret",
            "contract_text": "Sample text",
            "question": "What is the liability cap?"
        }
        res = client.post("/api/v1/rag/chat", json=payload, headers={"Authorization": "Bearer valid-b-token"})
        assert res.status_code == 404
        assert "not found or access denied" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_profile, None)
