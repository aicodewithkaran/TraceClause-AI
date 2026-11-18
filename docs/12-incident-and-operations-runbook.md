# 📘 TraceClause AI — Incident & Operations Runbook

This runbook provides actionable procedures for engineering and operations teams running TraceClause AI in production during the Beta phase (100–500 monthly active users, 10–20 paying customers).

---

## 1. Dedicated Background Worker Operations

### Architecture Summary
- **Ingestion**: FastAPI receives uploads and calls `public.create_contract_analysis_job` (<200ms).
- **Processing**: A standalone Render background worker process runs `python -m app.worker_daemon`.
- **Concurrency**: Controlled by `WORKER_CONCURRENCY` (configured to **2 concurrent jobs** for Beta).
- **Lease & Fencing**: Claimed via `FOR UPDATE SKIP LOCKED`. Every state update verifies `fencing_token`.

### Scenario 1.1: Worker Process Crashed or Terminated Mid-Job
1. **Automated Recovery**:
   - The `worker_daemon` runs an orphan janitor every 60 seconds.
   - Any job with `status = 'processing'` and `heartbeat_at < NOW() - 5 minutes` is automatically identified.
   - If `retry_count < max_retries` (default 3), the job is re-queued with `retry_count = retry_count + 1`.
   - If `retry_count >= max_retries`, the janitor invokes `public.fail_analysis_job`, marking it `failed`, purging staged text, and restoring user quota.
2. **Manual Inspection**:
   ```sql
   SELECT id, user_id, status, retry_count, fencing_token, heartbeat_at, stage_message
   FROM public.contract_analysis_jobs
   WHERE status = 'processing';
   ```
3. **Manual Job Reclaim**:
   ```sql
   UPDATE public.contract_analysis_jobs
   SET status = 'queued', locked_by = NULL, locked_at = NULL, stage_message = 'Manually re-queued by ops'
   WHERE id = '<JOB_UUID>' AND status = 'processing';
   ```

---

## 2. Emergency Circuit Breakers & Kill Switches

TraceClause AI includes operational kill switches that require zero redeployment—simply update the environment variable in Render and restart.

| Variable | Default | Purpose | Failure Behavior |
| :--- | :--- | :--- | :--- |
| `AI_PROCESSING_ENABLED` | `true` | Emergency shutoff for all LLM calls | Jobs/analysis reject with HTTP 503; worker refunds quota |
| `UPLOADS_ENABLED` | `true` | Emergency shutoff for file parsing | Upload endpoint rejects with HTTP 503 |
| `ALLOW_SYNCHRONOUS_ANALYSIS` | `false` | Gating for synchronous `/contract/analyze` | Returns HTTP 403 in production; enforces queue |
| `WORKER_CONCURRENCY` | `2` | Number of simultaneous jobs per worker | Bounded concurrency throttle |

### Scenario 2.1: OpenAI / Gemini Major Outage
1. Set `AI_PROCESSING_ENABLED=false` in the Render Web Service and Worker dashboards.
2. Active queued jobs will fail cleanly with the message:
   *"AI analysis is temporarily paused for scheduled maintenance. Quota has been refunded."*
3. No quota is lost; users see clear maintenance notifications rather than 500 errors.
4. Once upstream status pages show recovery, set `AI_PROCESSING_ENABLED=true`.

---

## 3. Razorpay Payments & Billing Operations

### Architecture Summary
- All pricing is server-authoritative (`PLAN_CATALOG`: Solo $79/mo, Team $299/mo).
- Orders are validated server-side; checkout uses Razorpay modal with HMAC-SHA256 signature verification.
- Fulfillment is single-transaction atomic via `public.fulfill_purchase`.
- Webhooks deduplicate on `event_id` in `public.processed_webhooks`.

### Scenario 3.1: Customer Reports Paid but Subscription Not Active
1. Look up the payment in the **Razorpay Dashboard**:
   - Verify payment status is **Captured**.
   - Note the `order_id` (e.g., `order_Q123456789`) and `payment_id` (e.g., `pay_P123456789`).
2. Check `public.purchases` table in Supabase:
   ```sql
   SELECT * FROM public.purchases WHERE razorpay_order_id = 'order_Q123456789';
   ```
3. If purchase is `pending` (e.g., customer closed tab before redirect and webhook was delayed):
   Execute manual fulfillment directly in Supabase SQL Editor:
   ```sql
   SELECT public.fulfill_purchase(
     'order_Q123456789',
     'pay_P123456789',
     7900,
     'USD',
     'manual_ops_override_' || NOW()::TEXT,
     'payment.captured'
   );
   ```
4. Verify user's profile now reflects `subscription_tier = 'solo'` and `subscription_expires_at = NOW() + 30 days`.

---

## 4. Database Janitor & Text Retention

### Staged Text Retention
- Contracts uploaded for queued analysis stage clean extracted text in `public.staged_job_payloads`.
- Staged text is **automatically purged** in the same transaction that completes or fails a job (`DELETE FROM public.staged_job_payloads WHERE job_id = p_job_id`).
- For jobs that encounter unexpected server crashes, run the 2-hour safety cleanup:
  ```sql
  DELETE FROM public.staged_job_payloads
  WHERE created_at < NOW() - INTERVAL '2 hours';
  ```

---

## 5. Health Monitoring & Key Telemetry

Monitor the following endpoints with Datadog, BetterStack, or Render Health Checks:

1. **Liveness Probe**: `GET /api/v1/health/live`
   - Response time: < 5ms.
   - Status: HTTP 200 `{"status": "alive"}`.
2. **Readiness Probe**: `GET /api/v1/health/ready`
   - Response time: < 50ms.
   - Status: HTTP 200 when database is healthy.
   - Alert thresholds:
     - `db_latency_ms > 250ms`: High database connection load.
     - `active_queue_depth > 15`: Consider increasing worker replicas or worker concurrency from 2 to 4.
     - `oldest_queued_job_age_seconds > 180s`: Queue lag alert—worker daemon may be stalled.

