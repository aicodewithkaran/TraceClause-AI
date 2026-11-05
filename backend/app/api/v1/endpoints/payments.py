import json
from fastapi import APIRouter, HTTPException, Request, Depends, status
from app.schemas.payment import (
    RazorpayOrderRequest, 
    RazorpayOrderResponse,
    RazorpayVerifyCheckoutRequest,
    RazorpayVerifyCheckoutResponse,
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
    Creates an authoritative Razorpay order.
    The client specifies only the plan tier; price and currency are looked up on the server.
    A pending purchase record is created in Supabase before the order is returned.
    """
    try:
        user_email = current_user.email or "customer@traceclause.ai"
        return payment_service.create_razorpay_order(current_user.id, user_email, req)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Razorpay order creation failed: {str(e)}"
        )

@router.post("/razorpay/verify-checkout", response_model=RazorpayVerifyCheckoutResponse)
async def verify_checkout(
    req: RazorpayVerifyCheckoutRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Verifies checkout completion from Razorpay modal:
    Validates cryptographic signature, queries Razorpay API directly,
    and activates entitlements via atomic fulfill_purchase stored procedure.
    """
    try:
        res = payment_service.verify_checkout_payment(req)
        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment verification failed: {res.message or res.status}"
            )
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Checkout verification failed: {str(e)}"
        )

@router.post("/razorpay/webhook", response_model=RazorpayWebhookResponse)
async def razorpay_webhook(request: Request):
    """
    Asynchronous Webhook receiver for Razorpay lifecycle events.
    Verifies HMAC-SHA256 signature, ensures idempotent processing, and activates
    subscription entitlements via atomic fulfill_purchase stored procedure.
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
            success=result.get("success", True),
            status=result.get("status", "processed"),
            message=result.get("message") or "Webhook processed successfully.",
            event_id=result.get("event_id")
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook event: {str(e)}"
        )
