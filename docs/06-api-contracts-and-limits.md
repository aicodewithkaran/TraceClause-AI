# 06. API Contracts & Token Budget Governance

This document contains the complete REST API endpoint reference table, rate-limiting rules, and LLM token governance policy for **ScanShield AI v2**.

---

## 🌐 REST API Endpoint Reference

| Method | Endpoint Route | Request Body | Success Response | Error Codes |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/upload` | `FormData (file: File)` | `{"contract_id": "c123", "filename": "msa.pdf", "lines": 45}` | `400` (Bad File), `413` (File $>50\text{MB}$) |
| `POST` | `/api/v1/analysis` | `{"contract_id": "c123", "playbook": "standard"}` | `ContractAnalysisResponse` | `402` (Limit Reached), `500` (LLM Error) |
| `POST` | `/api/v1/chat` | `{"contract_id": "c123", "question": "..."}` | `ChatCitationResponse` | `429` (Rate Limited), `404` (Doc Not Found) |
| `POST` | `/api/v1/billing/create-checkout` | `{"tier": "pro"}` | `{"checkout_url": "https://checkout.stripe.com/..."}` | `401` (Unauthorized) |
| `POST` | `/api/v1/billing/webhook` | `Stripe Event Payload` | `{"status": "success"}` | `400` (Invalid Signature) |

---

## 🪙 LLM Token Budget Governance Strategy

To optimize costs and prevent token exhaustion, model selection is tiered dynamically:

```
                      [User Request]
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
 [Fast Ingestion & Triage]       [Deep Legal Audit]
  • Model: gpt-4o-mini            • Model: claude-3.5-sonnet
  • Cost: $0.15 / 1M tokens       • Cost: $3.00 / 1M tokens
  • Purpose: Document line        • Purpose: Complex risk card
    parsing & classification        & redline counter-language
```

### Token Budget Limits Per Request:
- **Max Input Prompt Tokens:** $16,000$ tokens (via RAG candidate chunk filtering).
- **Max Output Generation Tokens:** $2,048$ tokens (enforced via Pydantic truncation).

---

## ⏱️ Rate-Limiting Policy (`slowapi` Middleware)

To prevent API abuse and DDOS attacks on LLM endpoints:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Rate Limits Applied:
# Anonymous uploads: 5 requests / minute
# Risk Audits: 10 requests / minute
# Citation Chat Queries: 20 requests / minute
```

When rate limits are exceeded, FastAPI responds with `HTTP 429 Too Many Requests`:
```json
{
  "error": "Rate limit exceeded. Maximum 10 contract risk audits per minute allowed."
}
```
