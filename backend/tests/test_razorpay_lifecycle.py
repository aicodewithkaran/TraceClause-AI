import hmac
import hashlib
import json
import pytest
from app.core.config import settings
from app.services.payment_service import PaymentService

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

def test_webhook_successful_payment_activation(client, monkeypatch):
    """Assert valid payment.captured webhook triggers entitlement activation for the user."""
    activated_users = []

    monkeypatch.setattr(PaymentService, "activate_subscription", lambda self, uid, tier: activated_users.append((uid, tier)))

    secret = settings.RAZORPAY_WEBHOOK_SECRET
    event_payload = {
        "id": "evt_test_payment_captured_001",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "amount": 7900,
                    "notes": {
                        "user_id": "test-user-id-5555",
                        "plan_tier": "solo"
                    }
                }
            }
        }
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    sig = generate_razorpay_signature(payload_bytes, secret)

    res = client.post("/api/v1/payments/razorpay/webhook", content=payload_bytes, headers={"X-Razorpay-Signature": sig})
    assert res.status_code == 200
    assert res.json()["status"] == "processed"
    assert len(activated_users) == 1
    assert activated_users[0] == ("test-user-id-5555", "solo")

def test_webhook_idempotency_duplicate_event(client, monkeypatch):
    """Assert duplicate webhook delivery with identical event_id is ignored idempotently."""
    event_payload = {
        "id": "evt_duplicate_test_002",
        "event": "order.paid",
        "payload": {
            "order": {
                "entity": {
                    "id": "order_test_456",
                    "notes": {
                        "user_id": "test-user-id-5555",
                        "plan_tier": "team"
                    }
                }
            }
        }
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    sig = generate_razorpay_signature(payload_bytes, settings.RAZORPAY_WEBHOOK_SECRET)

    # First call: processes event
    res1 = client.post("/api/v1/payments/razorpay/webhook", content=payload_bytes, headers={"X-Razorpay-Signature": sig})
    assert res1.status_code == 200

    # Second call: mock existing event in database
    class MockTable:
        def select(self, *args):
            return self
        def eq(self, *args):
            return self
        def execute(self):
            class MockData:
                data = [{"id": "existing-event-row"}]
            return MockData()

    class MockClient:
        def table(self, name):
            return MockTable()

    from app.api.v1.endpoints.payments import payment_service
    monkeypatch.setattr(payment_service, "supabase", MockClient())

    res2 = client.post("/api/v1/payments/razorpay/webhook", content=payload_bytes, headers={"X-Razorpay-Signature": sig})
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate_ignored"

def test_webhook_subscription_cancellation_downgrades(client, monkeypatch):
    """Assert subscription.cancelled event downgrades user to free tier."""
    downgraded_users = []
    monkeypatch.setattr(PaymentService, "downgrade_subscription", lambda self, uid: downgraded_users.append(uid))

    secret = settings.RAZORPAY_WEBHOOK_SECRET
    event_payload = {
        "id": "evt_test_sub_cancelled_003",
        "event": "subscription.cancelled",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_test_789",
                    "notes": {
                        "user_id": "test-user-id-5555"
                    }
                }
            }
        }
    }
    payload_bytes = json.dumps(event_payload).encode("utf-8")
    sig = generate_razorpay_signature(payload_bytes, secret)

    res = client.post("/api/v1/payments/razorpay/webhook", content=payload_bytes, headers={"X-Razorpay-Signature": sig})
    assert res.status_code == 200
    assert len(downgraded_users) == 1
    assert downgraded_users[0] == "test-user-id-5555"
