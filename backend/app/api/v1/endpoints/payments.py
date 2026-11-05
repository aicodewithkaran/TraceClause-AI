import json
from fastapi import APIRouter, HTTPException, Request, Depends, status
from app.schemas.payment import (
    RazorpayOrderRequest, 
    RazorpayOrderResponse,
    RazorpayWebhookResponse
)
from app.services.payment_service import PaymentService
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()
payment_service = PaymentService()

@router.post("/razorpay/create-order", response_model=RazorpayOrderResponse)
async def create_razorpay_order(
    req: RazorpayOrderRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Create a Razorpay order embedding the authenticated user's ID in server-controlled notes.
    Protected endpoint: Requires valid authenticated session.
    """
    try:
        user_email = current_user.email or "customer@traceclause.ai"
        return payment_service.create_razorpay_order(current_user.id, user_email, req)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Razorpay order creation failed: {str(e)}"
        )

@router.post("/razorpay/webhook", response_model=RazorpayWebhookResponse)
async def razorpay_webhook(request: Request):
    """
    Webhook receiver for Razorpay payment and subscription lifecycle events.
    Verifies HMAC-SHA256 signature, ensures idempotent processing, and activates
    subscription entitlements strictly from server-controlled metadata references.
    """
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Razorpay-Signature header."
        )

    raw_body = await request.body()
    is_valid = PaymentService.verify_razorpay_webhook_signature(raw_body, signature)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay webhook signature."
        )

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload."
        )

    try:
        result = payment_service.process_webhook_event(event_data)
        return RazorpayWebhookResponse(
            status=result.get("status", "processed"),
            message="Webhook event processed successfully.",
            event_id=result.get("event_id")
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook event: {str(e)}"
        )
