from pydantic import BaseModel, Field
from typing import Optional

class RazorpayOrderRequest(BaseModel):
    plan_tier: str = Field(..., description="solo or team")
    amount_usd: Optional[int] = Field(79, description="Amount in USD (e.g. 79 for Solo, 299 for Team)")

class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str

class RazorpayWebhookResponse(BaseModel):
    status: str
    message: str
    event_id: Optional[str] = None
