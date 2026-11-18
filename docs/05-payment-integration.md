# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 Payment & Monetization module manages multi-gateway subscriptions (Stripe for USD/International, Razorpay for INR/UPI/Cards with Razorpay payment link integration), delivers a dark glassmorphic checkout UI, tracks live quota metrics, and enforces tiered quota matrices across users and multi-seat workspaces.
* **Module Matrix (Version History)**:

| Payment Component | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **Payment Gateways** | Single-gateway Stripe | **Dual Gateways**: Stripe (USD) & Razorpay (INR/UPI/Cards) + **Razorpay Payment Link Integration** |
| **Checkout UI Design** | Standard redirect form | **Dark Glassmorphism Modal**: Animated strikethrough savings badges + Interactive USD ($) / INR (₹) toggle |
| **Free Quota** | Fixed 2 total reviews | **3 lifetime total audits** (Hard stop limit) |
| **Solo Quota ($79/mo)** | None | **20 reviews / month** (1 Seat, full redlines, RAG chat, `.docx` export) |
| **Team Quota ($299/mo)**| None | **100 reviews / month** (4 Seats pooled across workspace, shared workspace, custom playbook, priority SLA) |
| **Quota Reset Engine** | None | 30-Day Auto Reset Engine (`QuotaService` checking `last_quota_reset` timestamp) |
| **Live Quota Tracking** | Weekly quota counter | **Live Dynamic Quota Synchronization**: Backend returns `{ quota_used, limit, tier, remaining }` on every audit |
| **Workspace Creation**| None | Auto-provisioned `workspaces` record + seat assignment on Team plan payment |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI MONETIZATION & QUOTAS)

### Component: Multi-Gateway Billing & Tiered Quota Matrix Engine

* **Functional Description**: Coordinates international Stripe subscriptions, domestic India Razorpay UPI/Card payments, Razorpay payment link integration, multi-seat workspace auto-provisioning, 30-day quota resets, and live quota tracking via `quota_service.py`.
* **Technical Specs & Capabilities**:
  - **Supported Currencies**: USD (`$`), INR (`₹`).
  - **B2B Tier Matrix**:
    - **Free Trial**: 3 lifetime total audits (Hard stop limit).
    - **Solo Plan**: $79 USD / ₹7,499 INR per month (1 Seat, 20 reviews/mo).
    - **Team Plan**: $299 USD / ₹27,999 INR per month (4 Seats included, 100 reviews/mo pooled across workspace).
  - **Admin Service Role Key Access**: `QuotaService.get_supabase_client()` uses `SUPABASE_SERVICE_ROLE_KEY` to guarantee profile updates and quota increments bypass RLS policies.

* **Detailed Input/Output Data Dictionary**:

#### Live Quota Sync Response Payload (`QuotaService.check_and_increment_quota`)
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `quota_used` | `integer` | Count of audits executed in current period | Non-negative integer |
| `limit` | `integer` | Quota cap for active tier | `3` (Free), `20` (Solo), `100` (Team) |
| `tier` | `string` | User subscription tier | `'free'`, `'solo'`, `'team'` |
| `remaining` | `integer` | Audits remaining before quota stop | Non-negative integer |

* **Under-the-Hood Logic & Computations**:
  1. **Live Quota Check & Increment Logic**: `QuotaService.check_and_increment_quota(user_id)` checks `lifetime_free_audits_used` for Free tier (max 3), and `monthly_quota_used` for Solo (20/mo) and Team (100/mo pooled across workspace).
  2. **30-Day Monthly Quota Auto-Reset**: Compares current timestamp with `last_quota_reset`. If $> 30$ days have elapsed, `monthly_quota_used` is reset to 0 in Supabase and `last_quota_reset` is updated.
  3. **Team Workspace Pooled Quota Calculation**: For Team users, `QuotaService` inspects `workspace_members` to retrieve the workspace `owner_id` and aggregates usage against the owner's monthly pool (100 reviews/mo).
  4. **Razorpay Payment Link Integration**: `PaymentModal.tsx` integrates directly with Razorpay link checkout (`NEXT_PUBLIC_RAZORPAY_KEY_ID`), opening the secure Razorpay payment drawer for INR and international card payments.
  5. **Auto Workspace Provisioning**: On successful Team tier payment webhook / activation, `PaymentService.activate_subscription(user_id, 'team')` verifies if user owns a workspace. If not, it inserts a new record into `public.workspaces` with `seat_limit = 4` and adds the user as `owner` in `public.workspace_members`.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ERR_QUOTA_FREE` | 429 | Quota Service | Free user `lifetime_free_audits_used >= 3` | `Free trial limit reached (3/3 contracts). Please upgrade to Solo ($79) or Team ($299).` | Too Many Requests | HTTP 429 exception with upgrade prompt |
| `ERR_QUOTA_MONTHLY`| 429 | Quota Service | Monthly quota >= limit (20 Solo / 100 Team) | `Monthly contract review limit reached. Upgrade or purchase quota overage.` | Too Many Requests | HTTP 429 exception with upgrade prompt |
| `ERR_SIG_INVALID` | 400 | Webhook Listener | Invalid webhook HMAC signature | `Invalid signature` | Bad Request | Signature verification guard |
