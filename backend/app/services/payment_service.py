import hmac
import hashlib
import stripe
import razorpay
from app.core.config import settings
from app.schemas.payment import (
    StripeCheckoutRequest, 
    StripeCheckoutResponse, 
    RazorpayOrderRequest, 
    RazorpayOrderResponse,
    RazorpayVerificationRequest
)

from supabase import create_client, Client

class PaymentService:
    """Unified Payment Manager supporting Stripe (International) and Razorpay (Local/India)."""

    def __init__(self):
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY

        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            self.razorpay_client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
        else:
            self.razorpay_client = None

        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        else:
            self.supabase = None

    def create_stripe_checkout(self, req: StripeCheckoutRequest) -> StripeCheckoutResponse:
        if not settings.STRIPE_SECRET_KEY:
            # Return demo mock session if key not configured
            return StripeCheckoutResponse(
                checkout_url="https://checkout.stripe.com/demo_session",
                session_id="cs_demo_12345"
            )

        tier = req.plan_tier.lower()
        unit_amount = 29900 if tier == 'team' else 7900  # $299 or $79 in cents

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"TraceClause AI - {req.plan_tier.capitalize()} Plan Subscription",
                    },
                    'unit_amount': unit_amount,
                },
                'quantity': 1,
            }],
            mode='subscription',
            customer_email=req.user_email,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
        )

        return StripeCheckoutResponse(
            checkout_url=session.url,
            session_id=session.id
        )

    def create_razorpay_order(self, req: RazorpayOrderRequest) -> RazorpayOrderResponse:
        tier = req.plan_tier.lower()
        amount_inr = 27999 if tier == 'team' else 7499 # ₹27,999 or ₹7,499
        amount_paise = amount_inr * 100 # Convert to Paise

        if not self.razorpay_client:
            # Return demo mock order if keys not configured
            return RazorpayOrderResponse(
                order_id="order_demo_98765",
                amount=amount_paise,
                currency="INR",
                key_id=settings.RAZORPAY_KEY_ID or "rzp_test_demo"
            )

        order_data = {
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': f"receipt_{req.user_email}",
            'notes': {
                'plan_tier': req.plan_tier,
                'user_email': req.user_email
            }
        }

        order = self.razorpay_client.order.create(data=order_data)

        return RazorpayOrderResponse(
            order_id=order['id'],
            amount=order['amount'],
            currency=order['currency'],
            key_id=settings.RAZORPAY_KEY_ID
        )

    def verify_razorpay_signature(self, req: RazorpayVerificationRequest) -> bool:
        if not settings.RAZORPAY_KEY_SECRET:
            return True # Mock pass in test mode

        generated_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode('utf-8'),
            f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return generated_signature == req.razorpay_signature

    def activate_subscription(self, user_id: str, plan_tier: str):
        """Activates Solo or Team tier, updates quota, and provisions workspace for Team tier."""
        if not self.supabase:
            return

        tier = plan_tier.lower()
        if tier not in ['solo', 'team']:
            tier = 'solo'

        # Update profile subscription tier
        self.supabase.table("profiles").update({
            "subscription_tier": tier,
            "monthly_quota_used": 0
        }).eq("id", user_id).execute()

        # Provision Workspace if Team tier
        if tier == 'team':
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
