from fastapi import APIRouter, HTTPException, Request
from app.schemas.payment import (
    StripeCheckoutRequest, 
    StripeCheckoutResponse, 
    RazorpayOrderRequest, 
    RazorpayOrderResponse,
    RazorpayVerificationRequest
)
from app.services.payment_service import PaymentService

router = APIRouter()
payment_service = PaymentService()

@router.post("/stripe/create-checkout-session", response_model=StripeCheckoutResponse)
async def create_stripe_checkout(req: StripeCheckoutRequest):
    """Create a Stripe Checkout session for international subscriptions."""
    try:
        return payment_service.create_stripe_checkout(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe session creation failed: {str(e)}")

@router.post("/razorpay/create-order", response_model=RazorpayOrderResponse)
async def create_razorpay_order(req: RazorpayOrderRequest):
    """Create a Razorpay order for local/India payments (UPI, Cards, NetBanking)."""
    try:
        return payment_service.create_razorpay_order(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Razorpay order creation failed: {str(e)}")

@router.post("/razorpay/verify")
async def verify_razorpay_payment(req: RazorpayVerificationRequest):
    """Verify cryptographic signature for Razorpay successful payments."""
    is_valid = payment_service.verify_razorpay_signature(req)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature verification.")

    return {"status": "success", "message": "Payment verified successfully. Subscription activated!"}

@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe async webhooks for plan activation."""
    payload = await request.body()
    # In production, verify stripe webhook signature here
    return {"status": "received"}
