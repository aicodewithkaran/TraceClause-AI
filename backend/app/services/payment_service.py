import hmac
import hashlib
import json
import uuid
from typing import Optional, Dict, Any
import razorpay
from app.core.config import settings
from app.core.billing_config import PLAN_CATALOG
from app.schemas.payment import (
    RazorpayOrderRequest, 
    RazorpayOrderResponse,
    RazorpayVerifyCheckoutRequest,
    RazorpayVerifyCheckoutResponse
)
from supabase import create_client, Client

class PaymentService:
    """
    Authoritative Razorpay Payment Engine:
    - Server-controlled plan pricing and currency from PLAN_CATALOG.
    - Creates a server-side pending purchase record linked to the Razorpay order.
    - Double verification (signature match + direct server-to-server Razorpay API status fetch).
    - Single-transaction atomic entitlement fulfillment via PostgreSQL fulfill_purchase procedure.
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
        Creates an authoritative Razorpay order.
        Amount and currency are determined strictly on the server from PLAN_CATALOG.
        A pending purchase record is created in the database before returning the order.
        """
        tier = req.plan_tier.lower()
        if tier not in PLAN_CATALOG:
            tier = "solo"

        plan = PLAN_CATALOG[tier]
        amount_cents = plan["amount_cents"]
        currency = plan["currency"]
        purchase_id = str(uuid.uuid4())

        server_notes = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "plan_tier": tier
        }

        if not self.razorpay_client:
            # Mock order for testing / development without credentials
            mock_order_id = f"order_mock_{purchase_id[:8]}"
            if self.supabase:
                try:
                    self.supabase.table("purchases").insert({
                        "id": purchase_id,
                        "user_id": user_id,
                        "plan_tier": tier,
                        "amount_cents": amount_cents,
                        "currency": currency,
                        "status": "pending",
                        "razorpay_order_id": mock_order_id
                    }).execute()
                except Exception:
                    pass

            return RazorpayOrderResponse(
                purchase_id=purchase_id,
                order_id=mock_order_id,
                amount=amount_cents,
                currency=currency,
                key_id=settings.RAZORPAY_KEY_ID or "rzp_test_mock"
            )

        # 1. Create Order with Razorpay API
        order_data = {
            "amount": amount_cents,
            "currency": currency,
            "receipt": f"tc_{purchase_id[:8]}",
            "notes": server_notes
        }
        order = self.razorpay_client.order.create(data=order_data)
        razorpay_order_id = order["id"]

        # 2. Persist Pending Purchase Record in Supabase
        if self.supabase:
            try:
                self.supabase.table("purchases").insert({
                    "id": purchase_id,
                    "user_id": user_id,
                    "plan_tier": tier,
                    "amount_cents": amount_cents,
                    "currency": currency,
                    "status": "pending",
                    "razorpay_order_id": razorpay_order_id
                }).execute()
            except Exception as e:
                # In development or test mode, tolerate DB table absence before migration is executed
                if settings.ENVIRONMENT in ("development", "test"):
                    pass
                else:
                    raise RuntimeError(f"Failed to record pending purchase: {str(e)}")

        return RazorpayOrderResponse(
            purchase_id=purchase_id,
            order_id=razorpay_order_id,
            amount=amount_cents,
            currency=currency,
            key_id=settings.RAZORPAY_KEY_ID or ""
        )

    def verify_checkout_payment(self, req: RazorpayVerifyCheckoutRequest) -> RazorpayVerifyCheckoutResponse:
        """
        Verifies checkout completion from the Razorpay modal:
        1. Validates checkout cryptographic signature.
        2. Direct server-to-server check with Razorpay API to confirm captured status, expected order ID and amount.
        3. Invokes atomic fulfill_purchase stored procedure.
        """
        secret = settings.RAZORPAY_KEY_SECRET
        if not secret:
            # Fallback for mock environments
            return self._mock_fulfill_checkout(req)

        # 1. Verify Payment Signature
        expected_sig_str = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            expected_sig_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, req.razorpay_signature):
            return RazorpayVerifyCheckoutResponse(
                success=False,
                status="invalid_signature",
                message="Cryptographic payment signature mismatch."
            )

        # 2. Server-to-Server Payment Status Fetch
        if self.razorpay_client:
            try:
                payment = self.razorpay_client.payment.fetch(req.razorpay_payment_id)
                if payment.get("status") != "captured":
                    return RazorpayVerifyCheckoutResponse(
                        success=False,
                        status="payment_not_captured",
                        message=f"Payment status is {payment.get('status')}, expected captured."
                    )
                if payment.get("order_id") != req.razorpay_order_id:
                    return RazorpayVerifyCheckoutResponse(
                        success=False,
                        status="order_id_mismatch",
                        message="Payment order ID does not match checkout order."
                    )
                
                amount_cents = payment.get("amount", 0)
                currency = payment.get("currency", "USD")
            except Exception as e:
                return RazorpayVerifyCheckoutResponse(
                    success=False,
                    status="razorpay_verification_error",
                    message=f"Failed to verify payment with Razorpay: {str(e)}"
                )
        else:
            amount_cents = 7900
            currency = "USD"

        # 3. Atomic Database Fulfillment
        return self._execute_db_fulfillment(
            order_id=req.razorpay_order_id,
            payment_id=req.razorpay_payment_id,
            amount_cents=amount_cents,
            currency=currency
        )

    def _mock_fulfill_checkout(self, req: RazorpayVerifyCheckoutRequest) -> RazorpayVerifyCheckoutResponse:
        """Mock fulfillment helper for testing without Razorpay live keys."""
        return self._execute_db_fulfillment(
            order_id=req.razorpay_order_id,
            payment_id=req.razorpay_payment_id,
            amount_cents=7900,
            currency="USD"
        )

    def _execute_db_fulfillment(
        self, 
        order_id: str, 
        payment_id: str, 
        amount_cents: int, 
        currency: str, 
        event_id: Optional[str] = None, 
        event_type: str = "payment.captured"
    ) -> RazorpayVerifyCheckoutResponse:
        """Invokes the atomic fulfill_purchase PostgreSQL stored procedure."""
        if not self.supabase:
            return RazorpayVerifyCheckoutResponse(
                success=True,
                status="fulfilled_mock",
                plan_tier="solo",
                message="Subscription activated (mock DB mode)."
            )

        try:
            rpc_res = self.supabase.rpc("fulfill_purchase", {
                "p_order_id": order_id,
                "p_payment_id": payment_id,
                "p_amount_cents": amount_cents,
                "p_currency": currency,
                "p_event_id": event_id,
                "p_event_type": event_type
            }).execute()

            data = rpc_res.data or {}
            success = data.get("success", False)
            status_code = data.get("status") or data.get("error", "unknown")
            plan_tier = data.get("plan_tier")

            return RazorpayVerifyCheckoutResponse(
                success=success,
                status=status_code,
                plan_tier=plan_tier,
                message=data.get("message", "Fulfillment processed.")
            )
        except Exception as e:
            return RazorpayVerifyCheckoutResponse(
                success=False,
                status="db_error",
                message=f"Database fulfillment error: {str(e)}"
            )

    @staticmethod
    def verify_razorpay_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
        """Cryptographically verifies Razorpay HMAC-SHA256 webhook signature."""
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
        Processes Razorpay webhook event with strict verification:
        Only fulfills on verified captured events; ignores duplicates and mismatches cleanly.
        """
        event_id = event_data.get("id") or event_data.get("event_id") or ""
        event_type = event_data.get("event") or ""

        if not event_id:
            event_id = hashlib.sha256(json.dumps(event_data, sort_keys=True).encode("utf-8")).hexdigest()

        payload_container = event_data.get("payload", {})

        # Only fulfill on verified payment capture or order paid events
        if event_type in ("payment.captured", "order.paid"):
            payment_entity = payload_container.get("payment", {}).get("entity", {})
            order_entity = payload_container.get("order", {}).get("entity", {})

            order_id = payment_entity.get("order_id") or order_entity.get("id")
            payment_id = payment_entity.get("id")
            amount_cents = payment_entity.get("amount") or order_entity.get("amount", 0)
            currency = payment_entity.get("currency") or order_entity.get("currency", "USD")

            if order_id and payment_id:
                res = self._execute_db_fulfillment(
                    order_id=order_id,
                    payment_id=payment_id,
                    amount_cents=amount_cents,
                    currency=currency,
                    event_id=event_id,
                    event_type=event_type
                )
                return {
                    "success": res.success,
                    "status": res.status,
                    "event_id": event_id,
                    "message": res.message
                }

        # Handle cancellations / refunds by reverting tier to free
        if event_type in ("refund.processed", "subscription.cancelled", "subscription.halted"):
            payment_entity = payload_container.get("payment", {}).get("entity", {})
            order_id = payment_entity.get("order_id")
            if order_id and self.supabase:
                try:
                    p_res = self.supabase.table("purchases").select("user_id").eq("razorpay_order_id", order_id).execute()
                    if p_res.data and len(p_res.data) > 0:
                        user_id = p_res.data[0]["user_id"]
                        self.supabase.table("profiles").update({"subscription_tier": "free"}).eq("id", user_id).execute()
                except Exception:
                    pass

        return {
            "success": True,
            "status": "acknowledged",
            "event_id": event_id,
            "message": f"Webhook event {event_type} handled."
        }
