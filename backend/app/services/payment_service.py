import hmac
import hashlib
import json
from typing import Optional, Dict, Any
import razorpay
from app.core.config import settings
from app.schemas.payment import RazorpayOrderRequest, RazorpayOrderResponse
from supabase import create_client, Client

class PaymentService:
    """
    Razorpay Payment Engine managing Hosted Payment Page references and Webhook Entitlement Lifecycle.
    Stripe has been completely removed in accordance with production requirements.
    All subscription activations occur exclusively through cryptographically verified, idempotent webhooks.
    """

    def __init__(self):
        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            self.razorpay_client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
        else:
            self.razorpay_client = None

        if settings.SUPABASE_URL and settings.supabase_admin_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
        elif settings.SUPABASE_URL and settings.supabase_anon_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
        else:
            self.supabase = None

    def create_razorpay_order(self, user_id: str, user_email: str, req: RazorpayOrderRequest) -> RazorpayOrderResponse:
        """
        Creates an order embedding server-controlled references (user_id and plan_tier) in order notes.
        """
        tier = req.plan_tier.lower()
        if tier not in ("solo", "team"):
            tier = "solo"

        amount_usd = req.amount_usd or (299 if tier == "team" else 79)
        amount_cents = amount_usd * 100

        server_notes = {
            "user_id": user_id,
            "plan_tier": tier,
            "user_email": user_email
        }

        if not self.razorpay_client:
            # Safe mock order for development/testing
            return RazorpayOrderResponse(
                order_id="order_demo_dev",
                amount=amount_cents,
                currency="USD",
                key_id=settings.RAZORPAY_KEY_ID or "rzp_test_key"
            )

        order_data = {
            "amount": amount_cents,
            "currency": "USD",
            "receipt": f"tc_{user_id[:8]}",
            "notes": server_notes
        }

        order = self.razorpay_client.order.create(data=order_data)

        return RazorpayOrderResponse(
            order_id=order["id"],
            amount=order["amount"],
            currency=order["currency"],
            key_id=settings.RAZORPAY_KEY_ID or ""
        )

    @staticmethod
    def verify_razorpay_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
        """
        Cryptographically verifies Razorpay HMAC-SHA256 webhook signature.
        Fails closed: if secret is absent or signature doesn't match, returns False.
        """
        secret = settings.RAZORPAY_WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET
        if not secret or not signature_header:
            return False

        expected_sig = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_sig, signature_header)

    def process_webhook_event(self, event_data: dict) -> Dict[str, Any]:
        """
        Processes a Razorpay webhook event with strict idempotency and server-controlled reference matching.
        Covers payment captures, subscription activations, renewals, failures, refunds, and cancellations.
        """
        event_id = event_data.get("id") or event_data.get("event_id") or ""
        event_type = event_data.get("event") or ""

        if not event_id:
            # Fallback hash of event payload if id missing
            event_id = hashlib.sha256(json.dumps(event_data, sort_keys=True).encode("utf-8")).hexdigest()

        # 1. Idempotency Check: Verify if event has already been processed
        if self.supabase:
            try:
                check_res = self.supabase.table("processed_webhooks").select("id").eq("event_id", event_id).execute()
                if check_res.data and len(check_res.data) > 0:
                    return {"status": "duplicate_ignored", "event_id": event_id}
            except Exception:
                pass

        # 2. Extract Server-Controlled Metadata from Notes
        payload_container = event_data.get("payload", {})
        entity_obj = None

        for entity_key in ("payment", "order", "subscription", "refund"):
            if entity_key in payload_container and "entity" in payload_container[entity_key]:
                entity_obj = payload_container[entity_key]["entity"]
                break

        notes = entity_obj.get("notes", {}) if entity_obj else {}
        user_id = notes.get("user_id")
        plan_tier = notes.get("plan_tier") or "solo"

        # 3. Handle Lifecycle Events
        if user_id:
            if event_type in ("payment.captured", "order.paid", "subscription.activated", "subscription.charged"):
                self.activate_subscription(user_id, plan_tier)
            elif event_type in ("subscription.cancelled", "subscription.halted", "payment.failed"):
                self.downgrade_subscription(user_id)
            elif event_type == "refund.processed":
                self.downgrade_subscription(user_id)

        # 4. Record Processed Event for Idempotency
        if self.supabase:
            try:
                self.supabase.table("processed_webhooks").insert({
                    "event_id": event_id,
                    "event_type": event_type,
                    "provider": "razorpay",
                    "payload": event_data
                }).execute()
            except Exception:
                pass

        return {"status": "processed", "event_id": event_id, "event_type": event_type}

    def activate_subscription(self, user_id: str, plan_tier: str):
        """Activates Solo or Team tier, resets monthly quota, and provisions workspace for Team tier."""
        if not self.supabase:
            return

        tier = plan_tier.lower()
        if tier not in ("solo", "team"):
            tier = "solo"

        try:
            self.supabase.table("profiles").update({
                "subscription_tier": tier,
                "monthly_quota_used": 0
            }).eq("id", user_id).execute()

            # Provision Workspace if Team tier and none exists
            if tier == "team":
                ws_check = self.supabase.table("workspaces").select("id").eq("owner_id", user_id).execute()
                if not ws_check.data or len(ws_check.data) == 0:
                    prof_res = self.supabase.table("profiles").select("full_name").eq("id", user_id).single().execute()
                    owner_name = prof_res.data.get("full_name", "Team") if prof_res.data else "Team"

                    ws_res = self.supabase.table("workspaces").insert({
                        "owner_id": user_id,
                        "name": f"{owner_name}'s Workspace",
                        "seat_limit": 4
                    }).execute()

                    if ws_res.data and len(ws_res.data) > 0:
                        ws_id = ws_res.data[0]["id"]
                        self.supabase.table("workspace_members").insert({
                            "workspace_id": ws_id,
                            "user_id": user_id,
                            "role": "owner"
                        }).execute()
        except Exception:
            pass

    def downgrade_subscription(self, user_id: str):
        """Downgrades user profile back to free tier on cancellation, failure, or refund."""
        if not self.supabase:
            return
        try:
            self.supabase.table("profiles").update({
                "subscription_tier": "free"
            }).eq("id", user_id).execute()
        except Exception:
            pass
