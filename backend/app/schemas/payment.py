from pydantic import BaseModel, Field
from typing import Optional

class StripeCheckoutRequest(BaseModel):
    plan_tier: str = Field(..., description="pro or enterprise")
    user_email: str
    success_url: Optional[str] = "http://localhost:3000?payment=success"
    cancel_url: Optional[str] = "http://localhost:3000?payment=cancelled"

class StripeCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str

class RazorpayOrderRequest(BaseModel):
    plan_tier: str = Field(..., description="pro or enterprise")
    amount_inr: int = Field(..., description="Amount in INR (e.g. 1999 for ₹1999)")
    user_email: str

class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str

class RazorpayVerificationRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    user_email: str
