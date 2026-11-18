# Document 13: Staging Release Gate & Verification Runbook

> **Target Version:** TraceClause AI v2.0.0 Beta  
> **Audience:** Senior Software Engineers, DevOps, Security Reviewers  
> **Purpose:** Formal operational verification procedures for staging release before admitting paying customers (100–500 MAU, 10–20 paying clients).

---

## 1. Staging Release Gate Philosophy

A passing CI run (`pytest`, `tsc --noEmit`, Next.js build) verifies code syntax and unit assertions in isolation. It **does not** prove that:
- Deployed distributed processes (FastAPI web workers, dedicated background worker, Supabase PostgreSQL, Redis cache, Razorpay webhooks, and AI provider endpoints) coordinate correctly under network latency.
- Database migrations execute cleanly against live PostgreSQL instances without deadlocks.
- Worker process restarts safely recover in-flight jobs without duplicating reports or losing customer audit quota.

Therefore, **no code is promoted to public production without passing this Staging Release Gate.**

---

## 2. Staging Environment Topology

Staging must be an **exact mirror of production architecture**, strictly isolated from customer data:

| Component | Production | Staging Specification | Isolation Guarantee |
| :--- | :--- | :--- | :--- |
| **Frontend** | `app.traceclause.com` | `staging.traceclause.com` (Vercel Preview) | Distinct env vars & client build |
| **FastAPI Web Service** | Render Web (2 Uvicorn workers) | Render Web Staging (2 Uvicorn workers) | Separate Render service & logs |
| **Background Worker** | Render Background Worker | Render Staging Worker (`concurrency=2`) | Separate worker process & dyno |
| **Database & Auth** | Supabase Production | **Dedicated Supabase Staging Project** | Zero shared tables or customer records |
| **Distributed Cache** | Upstash Redis Production | Upstash Redis Staging | Distinct Redis database & keys |
| **Payment Gateway** | Razorpay Live (`rzp_live_*`) | **Razorpay Test Mode (`rzp_test_*`)** | Test cards only; no real transactions |
| **AI Providers** | OpenAI / Gemini / Anthropic Live | Dedicated Staging API Keys with **$5.00 Hard Ceiling** | Provider-side spend alerts & hard cap |

> [!CAUTION]
> **Never point the Staging environment at the production database or production AI keys.**  
> Always use synthetic test contracts (e.g. NDA, SaaS Agreement, Employment Agreement) or public SEC EDGAR agreements. Never upload confidential client data during staging tests.

---

## 3. Ten-Step End-to-End Verification Sequence

Execute this test sequence sequentially using a dedicated staging test account:

### Step 1: Authentication & Profile Initialization
- [ ] Sign up with a staging test email (`testuser+staging@traceclause.com`).
- [ ] Verify Magic Link / OTP authentication flow.
- [ ] Confirm row creation in `public.profiles` with `tier = 'free'`, `lifetime_free_audits_used = 0`, and initial quota intact.

### Step 2: Upload Robustness Matrix
Upload the following test payloads to `POST /api/v1/upload`:
1. **Small PDF (1-2 pages):** Must parse in `< 500ms`.
2. **Medium Contract (15-25 pages):** Must stream safely and extract all sections in `< 3s`.
3. **Near-Limit Document (90-95 pages):** Must pass page-count validation (`MAX_PAGE_COUNT = 100`).
4. **Invalid File Type (disguised .exe or .sh named .pdf):** Must fail closed with `HTTP 422 Unprocessable Content` (magic bytes mismatch).
5. **Corrupted PDF:** Must fail closed with `HTTP 422` with a friendly user message.
6. **Over-limit Payload (>15MB):** Must be terminated immediately via chunk streaming with `HTTP 413 Content Too Large`.
7. **Decompression Bomb (ZIP/DOCX ratio > 20:1):** Must be aborted with `HTTP 422`.

### Step 3: Asynchronous Queue Submission & Dedicated Worker Processing
- [ ] Submit an extracted contract to `POST /api/v1/jobs/submit`.
- [ ] Verify HTTP response time is **< 200ms** returning `status = 'queued'` and a unique `job_id`.
- [ ] Inspect PostgreSQL `contract_analysis_jobs`: verify row is locked with `status = 'processing'` and `fencing_token = 1`.
- [ ] Monitor polling endpoint `GET /api/v1/jobs/{job_id}/status`: verify live progress updates (20% -> 50% -> 80% -> 95% -> 100%).
- [ ] Verify heartbeats are continuously touched in the database during long LLM calls.

### Step 4: Analysis Output & Citations Integrity
- [ ] Confirm the generated report in `public.contract_reports` contains:
  - Valid `overall_risk_score` (`HIGH RISK`, `MEDIUM RISK`, or `LOW RISK`).
  - Clause-by-clause breakdown with title, category, explanation, and redline recommendation.
  - Linked `analysis_job_id` and matching `fencing_token`.
- [ ] Verify vector embeddings were generated and stored in `public.contract_embeddings`.
- [ ] Perform RAG query via `POST /api/v1/rag/chat`: verify grounded answer with clause citations.
- [ ] Export native Word document via `GET /api/v1/export/docx/{report_id}`: verify redlines and comments format cleanly.

### Step 5: Quota Accounting & Refund Integrity
- [ ] On audit completion: verify `public.quota_reservations` transitions to `committed`.
- [ ] Test failure path: trigger an intentional model failure (e.g. invalid key or timeout).
- [ ] Verify `public.fail_analysis_job` marks job `failed` and transitions quota reservation to `released`.
- [ ] Verify user's used audit count in `public.profiles` is decremented back to previous value.
- [ ] Attempt duplicate failure call: verify database returns `false` and **no double refund occurs**.

### Step 6: Text Privacy & Zero-Retention Staging Purge
- [ ] Check `public.staged_job_payloads` table after job completes or fails:
  ```sql
  SELECT COUNT(*) FROM public.staged_job_payloads WHERE job_id = 'YOUR_TEST_JOB_ID';
  ```
- [ ] **Must return 0.** Staged contract text must be wiped immediately upon terminal state.

### Step 7: Data Cleanup & Tenant Deletion
- [ ] Delete test report via `DELETE /api/v1/reports/{report_id}`.
- [ ] Verify cascade deletion removes all corresponding rows in `public.contract_embeddings`.
- [ ] Verify User A cannot delete or access User B's reports.

### Step 8: Razorpay Test-Mode Checkout & Order Verification
- [ ] Trigger Solo Plan upgrade ($79 / 30 days) from `PaymentModal`.
- [ ] Verify client queries `POST /api/v1/payments/razorpay/create-order` and receives authoritative server-priced order.
- [ ] Complete transaction using Razorpay Test Card (`4111 1111 1111 1111`).
- [ ] Verify client verification `POST /api/v1/payments/razorpay/verify-checkout` validates cryptographic HMAC SHA-256 signature.
- [ ] Confirm `public.profiles` updates: `tier = 'solo'`, `billing_status = 'active'`, and `plan_expires_at = NOW() + INTERVAL '30 days'`.

### Step 9: Webhook Idempotency & Replay Protection
- [ ] Replay the identical Razorpay webhook payload (`order.paid` or `payment.captured`) using curl:
  ```bash
  curl -X POST https://api-staging.traceclause.com/api/v1/payments/razorpay/webhook \
    -H "X-Razorpay-Signature: <VALID_HMAC>" \
    -H "Content-Type: application/json" \
    -d '<PAYLOAD>'
  ```
- [ ] Verify endpoint returns HTTP 200 with `status = "already_processed"` or idempotency guard.
- [ ] Confirm user entitlement was **not doubled or extended twice**.

### Step 10: Multi-Tenant Cross-User Isolation
- [ ] Create two distinct accounts: User Alpha and User Beta.
- [ ] User Alpha submits an audit and generates report `rep_alpha_01`.
- [ ] User Beta attempts:
  - `GET /api/v1/reports/rep_alpha_01` -> **Must return HTTP 404/403**.
  - `GET /api/v1/jobs/{alpha_job_id}/status` -> **Must return HTTP 404/403**.
  - `POST /api/v1/rag/chat` referencing `contract_id = rep_alpha_01` -> **Must return HTTP 404/403**.
  - `GET /api/v1/export/docx/rep_alpha_01` -> **Must return HTTP 404/403**.

---

## 4. Failure, Resilience & Load Testing

Execute these tests in Staging only:

### Test A: Worker Crash & Recovery During Active Audit
1. Submit a 20-page contract audit.
2. When progress reaches 50%, terminate the worker process abruptly (`kill -9 <pid>`).
3. Allow heartbeat to expire (2 minutes in staging).
4. Start a new worker instance.
5. **Expected Outcome:**
   - Worker daemon orphan janitor reclaims the job.
   - Fencing token increments (`token = 2`).
   - Prior partial report and embeddings are cleaned up atomically.
   - Job completes successfully under `token = 2`.
   - If old worker miraculously wakes up and attempts `complete_analysis_job` with `token = 1`, database returns `false` and rejects it.

### Test B: Durable AI Budget Cap Gate
1. Set staging database cap to a low test value ($0.05 / 50,000 microdollars):
   ```sql
   UPDATE public.ai_budget_periods 
   SET cap_microdollars = 50000 
   WHERE scope = 'global';
   ```
2. Submit a contract audit.
3. **Expected Outcome:**
   - Pre-call check in `llm_analyzer.py` triggers `reserve_ai_budget`.
   - Stored procedure detects `actual + reserved + requested > cap` and returns `BUDGET_EXCEEDED`.
   - Job is aborted with clear user-facing error: `"Monthly AI budget limit reached. Quota has been refunded to your account."`
   - User's audit quota is preserved.
   - Zero billable calls reach the AI provider.

### Test C: Shared Redis Rate Limiting Under Multi-Worker Concurrency
1. Verify `IPRateLimitMiddleware` enforces 60 req/min across both Uvicorn worker processes.
2. Forge `X-Forwarded-For: 1.1.1.1` from an untrusted client: verify socket IP is used and rate limit cannot be evaded.
3. Test upload rate limit: submit 6 rapid uploads from User Alpha. Verify 6th upload returns `HTTP 429` with `Retry-After: 60`.
4. Stop Redis container in staging:
   - Submit upload: verify **fails closed** with `HTTP 503` (prevents unmetered load).
   - Query `/health/live`: verify **remains available** (low-risk endpoints do not crash).

### Test D: Gradual Load Staging Ramp
1. **Tier 1 (5 concurrent users):** Verify average job completion time `< 30 seconds`.
2. **Tier 2 (20 concurrent audits):** Monitor worker memory consumption. Must remain `< 512MB RAM`. Zero OOM events.
3. **Tier 3 (50 queued jobs):** Verify PostgreSQL connection pool remains healthy (`< 20 connections`). All jobs process in FIFO order without orphan leakage.

---

## 5. Staging Sign-Off Evidence Log Template

Before deploying any commit to production, complete and commit this sign-off record:

```markdown
### Staging Release Verification Record

- **Date & UTC Time:** 2026-11-18 17:00 UTC
- **Git Commit Hash:** [e.g. 7b343c04979bb2496c8b39a336185acbcf15036e]
- **Applied Database Migrations:** 
  - `20261105_production_master_hardening.sql`
  - `20261118_durable_ai_budget_and_fenced_cleanup.sql`
- **Environment Services:**
  - FastAPI Web: Render Web Service (2 Uvicorn instances)
  - Worker: Render Dedicated Worker (concurrency=2)
  - PostgreSQL: Supabase Staging (15.x, pgvector enabled)
  - Redis: Upstash Staging
- **Test Results Summary:**
  - Automated Unit/Integration Tests: 60 / 60 Passed (0 failures)
  - TypeScript Type Check (`tsc --noEmit`): 0 Errors
  - E2E 10-Step Test Sequence: PASSED (Steps 1-10 verified)
  - Worker Kill & Resume Test: PASSED (Fencing token incremented, zero duplicates)
  - AI Budget Cap Trip Test: PASSED (Hard limit locked in DB, quota restored)
  - Razorpay Test Webhook Replay: PASSED (Idempotent 200, no double entitlement)
  - Cross-Tenant Isolation: PASSED (Zero data leaks between Alpha and Beta)
- **Observed Metrics:**
  - Peak Worker RAM: 242 MB
  - Average Single Audit Time: 18.4 seconds
  - Total AI Spend Incurred in Staging: $0.14 USD
- **Sign-off Engineers:**
  - Senior Software Engineer: Karan Singh (@aicodewithkaran)
  - Verification Status: **APPROVED FOR BETA LAUNCH**
```

