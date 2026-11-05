from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class RazorpayOrderRequest(BaseModel):
    """
    Client specifies only the desired plan identifier.
    Pricing, currency, and intervals are strictly looked up on the server.
    """
    plan_tier: str = Field(..., description="solo or team")

class RazorpayOrderResponse(BaseModel):
    purchase_id: str
    order_id: str
    amount: int
    currency: str
    key_id: str

class RazorpayVerifyCheckoutRequest(BaseModel):
    """
    Payload returned by Razorpay Checkout modal after user completes payment.
    """
    purchase_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class RazorpayVerifyCheckoutResponse(BaseModel):
    success: bool
    status: str
    plan_tier: Optional[str] = None
    message: Optional[str] = None

class RazorpayWebhookResponse(BaseModel):
    success: bool
    status: str
    message: Optional[str] = "Webhook processed successfully."
    event_id: Optional[str] = None
