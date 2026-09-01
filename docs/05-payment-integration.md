# 05. Payment Integration & Monetization Logic

This document details the **Stripe Billing Integration**, credit tracking engine, webhook listeners, and tier quotas for **ScanShield AI v2**.

---

## 💳 Pricing Tiers & Metered Usage Blueprint

```
 ┌─────────────────────────────────────────────────────────────┐
 │                      SUBSCRIPTION TIERS                     │
 ├──────────────────────────────┬──────────────────────────────┤
 │         FREE TIER            │          PRO TIER            │
 │     $0 / month               │     $49 / month              │
 │ • 2 Free Contract Audits     │ • Unlimited Contract Audits  │
 │ • Standard Risk Extraction   │ • Custom Playbooks           │
 │ • Basic PDF Export           │ • Instant Redline Generator  │
 └──────────────────────────────┴──────────────────────────────┘
```

---

## 🔄 Stripe Checkout Flow

1. User clicks **"Upgrade to Pro"** on the Next.js frontend.
2. Next.js triggers `POST /api/v1/billing/create-checkout-session`.
3. FastAPI creates a Stripe Checkout Session via the official `stripe` Python SDK:

```python
import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_stripe_checkout(user_id: str, user_email: str):
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        customer_email=user_email,
        client_reference_id=user_id,
        line_items=[{
            'price': settings.STRIPE_PRO_PRICE_ID,
            'quantity': 1,
        }],
        mode='subscription',
        success_url=f"{settings.FRONTEND_URL}/dashboard?payment=success",
        cancel_url=f"{settings.FRONTEND_URL}/dashboard?payment=cancelled",
    )
    return session.url
```

---

## ⚡ Stripe Webhook Event Listeners (`routers/billing.py`)

FastAPI handles incoming webhooks to update user subscription status in Supabase:

```python
from fastapi import APIRouter, Request, HTTPException
import stripe

router = APIRouter()

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Event Router
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        # Grant Pro Access in Database
        update_user_tier(user_id=user_id, tier="pro")

    elif event['type'] == 'invoice.payment_failed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        # Revoke Pro Access / Downgrade
        update_user_tier(user_id=user_id, tier="free")

    return {"status": "success"}
```

---

## 📊 Credit Consumption & Quota Enforcement

- Every contract upload checks `user.credits_remaining`.
- Free users start with **2 credits**.
- When `credits_remaining == 0`, API returns HTTP `402 Payment Required` with body:
  `{"detail": "Free contract limit reached. Upgrade to Pro for unlimited contract risk audits."}`
