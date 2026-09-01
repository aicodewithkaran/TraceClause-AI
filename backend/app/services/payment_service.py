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

    def create_stripe_checkout(self, req: StripeCheckoutRequest) -> StripeCheckoutResponse:
        if not settings.STRIPE_SECRET_KEY:
            # Return demo mock session if key not configured
            return StripeCheckoutResponse(
                checkout_url="https://checkout.stripe.com/demo_session",
                session_id="cs_demo_12345"
            )

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"ScanShield AI - {req.plan_tier.capitalize()} Plan Subscription",
                    },
                    'unit_amount': 2900 if req.plan_tier.lower() == 'pro' else 9900, # $29 or $99
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
        amount_paise = req.amount_inr * 100 # Convert to Paise

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
