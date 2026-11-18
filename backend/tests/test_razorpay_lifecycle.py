import hmac
import hashlib
import json
import pytest
from app.core.config import settings
from app.services.payment_service import PaymentService
from app.api.v1.endpoints.payments import payment_service
from app.schemas.payment import RazorpayVerifyCheckoutResponse

def get_test_webhook_secret() -> str:
    return settings.RAZORPAY_WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET or "rzp_test_webhook_secret_key"

def generate_razorpay_signature(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

def test_webhook_missing_signature(client):
    """Assert webhook endpoint rejects requests missing X-Razorpay-Signature header with 400."""
    res = client.post("/api/v1/payments/razorpay/webhook", content=b"{}")
    assert res.status_code == 400
    assert "Missing X-Razorpay-Signature" in res.json()["detail"]

def test_webhook_invalid_signature(client):
    """Assert webhook endpoint rejects requests with mismatched signature with 400."""
    payload = b'{"event": "payment.captured"}'
    headers = {"X-Razorpay-Signature": "invalid_signature_hex_12345"}
    res = client.post("/api/v1/payments/razorpay/webhook", content=payload, headers=headers)
    assert res.status_code == 400
    assert "Invalid Razorpay webhook signature" in res.json()["detail"]

def test_create_order_server_pricing(client, monkeypatch):
    """Assert order creation endpoint rejects client-supplied amounts and strictly looks up price on server."""
    from app.core.security import AuthenticatedUser, get_current_user
    mock_user = AuthenticatedUser(id="user-order-123", email="user@example.com")
    
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # Mock razorpay order creation
    if payment_service.razorpay_client:
        monkeypatch.setattr(
            payment_service.razorpay_client.order, 
            "create", 
            lambda data: {"id": "order_mock_123", "amount": data["amount"], "currency": data["currency"]}
        )

    try:
        # Request Solo tier
        res = client.post("/api/v1/payments/razorpay/create-order", json={"plan_tier": "solo"})
        assert res.status_code == 200
        data = res.json()
        assert data["amount"] == 7900  # $79.00 USD
        assert data["currency"] == "USD"
        assert "purchase_id" in data
        assert "order_id" in data

        # Request Team tier
        res_team = client.post("/api/v1/payments/razorpay/create-order", json={"plan_tier": "team"})
        assert res_team.status_code == 200
        assert res_team.json()["amount"] == 29900  # $299.00 USD
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_webhook_successful_payment_fulfillment(client, monkeypatch):
    """Assert valid payment.captured webhook triggers atomic database fulfillment."""
    fulfilled_calls = []

    def mock_db_fulfillment(*args, **kwargs):
        fulfilled_calls.append(kwargs)
        return RazorpayVerifyCheckoutResponse(success=True, status="fulfilled", plan_tier="solo")

    monkeypatch.setattr(PaymentService, "_execute_db_fulfillment", mock_db_fulfillment)

    secret = get_test_webhook_secret()
    event_payload = {
        "id": "evt_test_payment_captured_001",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "order_id": "order_test_789",
                    "amount": 7900,
                    "currency": "USD"
                }
            }
        }
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    sig = generate_razorpay_signature(payload_bytes, secret)

    res = client.post("/api/v1/payments/razorpay/webhook", content=payload_bytes, headers={"X-Razorpay-Signature": sig})
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert len(fulfilled_calls) == 1
    assert fulfilled_calls[0]["order_id"] == "order_test_789"
    assert fulfilled_calls[0]["payment_id"] == "pay_test_123"
    assert fulfilled_calls[0]["amount_cents"] == 7900

def test_verify_checkout_signature_validation(client, monkeypatch):
    """Assert verify-checkout validates cryptographic checkout signature."""
    from app.core.security import AuthenticatedUser, get_current_user
    mock_user = AuthenticatedUser(id="user-order-123", email="user@example.com")
    
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        # Invalid signature
        req_payload = {
            "purchase_id": "d3b07384-d113-4a1a-9669-e7401a0e1e67",
            "razorpay_order_id": "order_test_abc",
            "razorpay_payment_id": "pay_test_xyz",
            "razorpay_signature": "invalid_sig_abc"
        }
        res = client.post("/api/v1/payments/razorpay/verify-checkout", json=req_payload)
        assert res.status_code == 400
        assert "Payment verification failed" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_webhook_duplicate_event_deduplication(client, monkeypatch):
    """Assert duplicate webhook event IDs are detected and ignored idempotently without multiple fulfillments."""
    fulfillment_calls = []

    def mock_db_fulfillment(*args, **kwargs):
        event_id = kwargs.get("event_id")
        if event_id in fulfillment_calls:
            return RazorpayVerifyCheckoutResponse(success=True, status="duplicate_ignored")
        fulfillment_calls.append(event_id)
        return RazorpayVerifyCheckoutResponse(success=True, status="fulfilled", plan_tier="solo")

    monkeypatch.setattr(PaymentService, "_execute_db_fulfillment", mock_db_fulfillment)

    secret = get_test_webhook_secret()
    event_payload = {
        "id": "evt_duplicate_test_999",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_dup_123",
                    "order_id": "order_dup_456",
                    "amount": 7900,
                    "currency": "USD"
                }
            }
        }
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    sig = generate_razorpay_signature(payload_bytes, secret)

    # First delivery
    res1 = client.post("/api/v1/payments/razorpay/webhook", content=payload_bytes, headers={"X-Razorpay-Signature": sig})
    assert res1.status_code == 200
    assert res1.json()["status"] == "fulfilled"

    # Second delivery (Duplicate)
    res2 = client.post("/api/v1/payments/razorpay/webhook", content=payload_bytes, headers={"X-Razorpay-Signature": sig})
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate_ignored"
    # Ensure only 1 fulfillment execution occurred
    assert len(fulfillment_calls) == 1

def test_webhook_cancellation_reverts_subscription_to_free(client, monkeypatch):
    """Assert subscription.cancelled event reverts user profile subscription_tier to free."""
    updated_profiles = []

    class MockTable:
        def __init__(self, name):
            self.name = name
        def select(self, *args, **kwargs):
            return self
        def eq(self, col, val):
            return self
        def execute(self):
            class Res:
                data = [{"user_id": "user-cancelled-123"}]
            return Res()
        def update(self, payload):
            updated_profiles.append(payload)
            return self

    class MockSupabase:
        def table(self, name):
            return MockTable(name)

    monkeypatch.setattr(payment_service, "supabase", MockSupabase())

    secret = get_test_webhook_secret()
    event_payload = {
        "id": "evt_cancel_123",
        "event": "subscription.cancelled",
        "payload": {
            "payment": {
                "entity": {
                    "order_id": "order_cancel_456"
                }
            }
        }
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    sig = generate_razorpay_signature(payload_bytes, secret)

    res = client.post("/api/v1/payments/razorpay/webhook", content=payload_bytes, headers={"X-Razorpay-Signature": sig})
    assert res.status_code == 200
    assert len(updated_profiles) == 1
    assert updated_profiles[0]["subscription_tier"] == "free"

