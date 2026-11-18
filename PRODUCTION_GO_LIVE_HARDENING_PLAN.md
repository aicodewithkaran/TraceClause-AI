# 🚀 TraceClause AI — Production Go-Live & Enterprise Scale Hardening Plan
**Classification:** Enterprise Engineering Roadmap & Implementation Plan  
**Target Goal:** Support 100s–1,000s of monthly active users and 100+ simultaneous contract audits with zero downtime and <0.1% error rate.  
**Target Environment:** Next.js 16 (Vercel) / FastAPI 0.115 (Render / Docker) / Supabase pgvector / Razorpay  

---

## Executive Architecture Summary

TraceClause AI currently has solid foundational security: Supabase Row-Level Security (RLS), column-level update grants, trigger protections, atomic quota stored procedures, Razorpay HMAC-SHA256 verification, and native Word `.docx` redline exports.

However, to transition from a **Private Beta (1–10 concurrent users)** to **Enterprise Scale (100+ simultaneous users)**, the system must resolve 5 critical architectural bottlenecks:
1. **x:** CPU-bound PDF parsing and synchronous LLM calls run directly inside `async def` routes, halting the event loop.
2. **Frontend Queue Disconnect:** The UI calls the synchronous `/contract/analyze` endpoint instead of the asynchronous PostgreSQL job queue (`/jobs/submit`), causing 504 Gateway Timeouts on long contracts.
3. **Silent Mock Fallback on Rate Limits:** When upstream LLMs return HTTP 429, the system catches the exception and immediately returns canned mock data without retrying.
4. **Upload Semaphore Constriction:** An in-memory semaphore restricts uploads to 3 concurrent operations per process.
5. **Database Connection Limits:** High concurrency requires routing queries through Supabase's Supavisor connection pooler (port 6543).

---

## Phase Breakdown & Work Execution Matrix

```mermaid
gantt
    title TraceClause AI Production Go-Live Implementation
    dateFormat  YYYY-MM-DD
    section Phase 1 : Core Concurrency
    Event Loop Unblocking (asyncio.to_thread)       :active, p1_1, 2026-11-19, 1d
    Frontend Background Queue Wiring                :active, p1_2, 2026-11-20, 2d
    Tenacity LLM Retry & Exponential Backoff       :active, p1_3, 2026-11-21, 1d
    section Phase 2 : Scalability & Infra
    Uvicorn Multi-Worker & Docker Optimization     :p2_1, 2026-11-22, 1d
    Supavisor DB Connection Pooling (Port 6543)    :p2_2, 2026-11-23, 1d
    Standalone Queue Daemon Decoupling             :p2_3, 2026-11-24, 2d
    section Phase 3 : Commercial Launch
    Razorpay Live Mode & International Compliance  :p3_1, 2026-11-25, 1d
    Transactional Email Notifications (Resend)     :p3_2, 2026-11-26, 1d
    End-to-End Locust Load Testing (100 Users)     :p3_3, 2026-11-27, 1d
```

---

## PHASE 1: Core Concurrency Fixes (Mandatory Before Selling)
*Estimated Timeline: 2–3 Days*  
*Objective: Eliminate event loop freezes, prevent gateway timeouts, and guarantee real AI analysis under rate limit spikes.*

### Task 1.1: Unblock the FastAPI Event Loop
**Problem:** In `upload.py` and `analysis.py`, heavy CPU parsing and network LLM calls are invoked directly inside `async def` endpoints, blocking the single-threaded asyncio event loop for 15–45 seconds per request.

**File Changes:**
- **File 1:** [`backend/app/api/v1/endpoints/upload.py`](backend/app/api/v1/endpoints/upload.py)
  - Offload `DocumentParser.parse_document` to a worker thread:
    ```python
    # Before:
    extracted_text = DocumentParser.parse_document(file_bytes, filename)
    
    # After:
    extracted_text = await asyncio.to_thread(DocumentParser.parse_document, file_bytes, filename)
    ```
- **File 2:** [`backend/app/api/v1/endpoints/analysis.py`](backend/app/api/v1/endpoints/analysis.py)
  - Offload `analyzer.analyze_clauses` to a worker thread:
    ```python
    # Before:
    result = analyzer.analyze_clauses(file_name, extracted_text, clauses)
    
    # After:
    result = await asyncio.to_thread(analyzer.analyze_clauses, file_name, extracted_text, clauses)
    ```

---

### Task 1.2: Wire Frontend `Dropzone.tsx` to the Background Job Queue
**Problem:** The frontend currently makes a synchronous HTTP POST to `/contract/analyze`. For documents $>30$ pages or under load, proxies (Cloudflare, Render, Vercel) time out with HTTP 504 Gateway Timeout. The backend's durable queue (`/jobs/submit`, `contract_analysis_jobs`, `JobWorker`) is already implemented but unused by the client.

**File Changes:**
- **File 1:** [`frontend/src/lib/api-client.ts`](frontend/src/lib/api-client.ts)
  - Add job submission and polling helper methods:
    ```typescript
    async submitAnalysisJob(
      fileName: string,
      extractedText: string,
      retainAudit: boolean = true,
      workspaceId?: string
    ): Promise<{ job_id: string; status: string }> {
      const headers = await getAuthHeaders();
      const res = await axios.post(
        `${API_BASE_URL}/jobs/submit`,
        { file_name: fileName, extracted_text: extractedText, retain_audit: retainAudit, workspace_id: workspaceId },
        { headers }
      );
      return res.data;
    },

    async getJobStatus(jobId: string): Promise<{
      id: string;
      status: 'queued' | 'processing' | 'completed' | 'failed';
      progress_percent: number;
      stage_message: string;
      result?: any;
      error_message?: string;
    }> {
      const headers = await getAuthHeaders();
      const res = await axios.get(`${API_BASE_URL}/jobs/${jobId}`, { headers });
      return res.data;
    }
    ```
- **File 2:** [`frontend/src/components/upload/Dropzone.tsx`](frontend/src/components/upload/Dropzone.tsx)
  - Replace synchronous `apiClient.analyzeContract` with job submission and polling:
    1. Call `apiClient.submitAnalysisJob(...)` receiving `job_id`.
    2. Start polling `apiClient.getJobStatus(job_id)` every 1,500ms.
    3. Update the UI state with real-time `stage_message` and `progress_percent` (e.g., "Extracting clauses 20%...", "Evaluating legal risks 50%...", "Indexing embeddings 80%...").
    4. On `status === 'completed'`, pass `result` to `onAnalysisComplete(result)`.
    5. On `status === 'failed'`, surface clean user-friendly error message.

---

### Task 1.3: Implement Tenacity Exponential Backoff Retry in `LLMAnalyzer`
**Problem:** Under concurrent loads, OpenAI, Gemini, or Anthropic return HTTP 429 (Rate Limit). Currently, `llm_analyzer.py` catches all exceptions and silently defaults to `_mock_analysis`, giving paying customers canned placeholder text.

**File Changes:**
- **File:** [`backend/app/services/llm_analyzer.py`](backend/app/services/llm_analyzer.py)
  - Add `tenacity` retry with random exponential jitter:
    ```python
    from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

    class LLMAnalyzer:
        @retry(
            wait=wait_random_exponential(min=1, max=12),
            stop=stop_after_attempt(4),
            reraise=True
        )
        def _execute_provider_call(self, batch):
            # Calls OpenAI / Gemini / Anthropic with automatic retries on rate limits
    ```
  - Raise explicit `HTTPException(status_code=503, detail="AI provider busy, please retry in a moment")` only if 4 retries fail, rather than silently injecting mock data into real legal contracts.

---

## PHASE 2: Scalability, Concurrency & Infrastructure Hardening
*Estimated Timeline: 2–3 Days*  
*Objective: Guarantee stability for 100+ simultaneous audits without memory exhaustion or database lockups.*

### Task 2.1: Multi-Worker Uvicorn Deployment Configuration
**Problem:** A single Uvicorn process is bounded by Python's single thread. If 100 requests arrive, they contend for one CPU core.

**Implementation:**
- Configure Render web service start command:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --timeout-keep-alive 65
  ```
- Or deploy via Dockerfile with Gunicorn process manager:
  ```dockerfile
  CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--timeout", "120", "app.main:app"]
  ```

---

### Task 2.2: Concurrency & Parsing Semaphore Tuning
**Problem:** `upload_semaphore = asyncio.Semaphore(3)` in `upload.py` is too restrictive, queuing 97 out of 100 simultaneous users.

**Implementation:**
- Increase worker semaphore to `asyncio.Semaphore(10)` per process.
- Across 4 Uvicorn workers, this permits **40 concurrent in-flight PDF parsing operations** without exceeding container RAM limits (assuming standard 2GB RAM container on Render).

---

### Task 2.3: Database Connection Pooling via Supavisor
**Problem:** 100 concurrent users will exhaust PostgreSQL's direct connection limits (default 60–100 slots).

**Implementation:**
- In `backend/.env`, configure connection strings to use Supabase's managed connection pooler:
  ```env
  # Use Transaction Mode pooler on port 6543
  DATABASE_URL="postgres://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?pgbouncer=true"
  ```
- Ensures thousands of client connections are multiplexed over a pool of 15–20 server connections.

---

### Task 2.4: Standalone Background Queue Daemon Decoupling
**Problem:** `background_tasks.add_task(worker.claim_and_run_one)` in FastAPI executes inside the web request container. If the web container restarts during a deploy, in-flight background tasks die.

**Implementation:**
- Create a dedicated worker entrypoint: `backend/app/worker_daemon.py`:
  ```python
  import asyncio
  from app.services.job_worker import JobWorker

  async def main():
      worker = JobWorker()
      while True:
          claimed = worker.claim_and_run_one()
          if not claimed:
              await asyncio.sleep(1.0)

  if __name__ == "__main__":
      asyncio.run(main())
  ```
- Run on Render as a dedicated background worker service (`python -m app.worker_daemon`).

---

## PHASE 3: Commercial Launch & Payment Go-Live
*Estimated Timeline: 1–2 Days*  
*Objective: Enable live money transactions, international cards, and automated customer communications.*

### Task 3.1: Razorpay Live Mode Transition & International Payment Compliance
**Actions:**
1. Switch credentials in production environment variables:
   - Backend: Replace `RAZORPAY_KEY_ID` (starts with `rzp_live_...`) and `RAZORPAY_KEY_SECRET`.
   - Frontend: Update `NEXT_PUBLIC_RAZORPAY_KEY_ID`.
2. Enable **International Cards** in the Razorpay Dashboard:
   - Go to *Razorpay Dashboard $\to$ Settings $\to$ Payment Methods $\to$ International Cards $\to$ Enable*.
   - Required for customers in the US, Europe, and Asia purchasing the **Solo Plan ($79 USD)** and **Team Plan ($299 USD)**.
3. Configure Production Webhook URL in Razorpay Dashboard:
   - URL: `https://your-backend.onrender.com/api/v1/payments/razorpay/webhook`
   - Secret: Matches `RAZORPAY_WEBHOOK_SECRET` in `.env`.
   - Events: `payment.captured`, `order.paid`, `refund.processed`, `subscription.cancelled`.

---

### Task 3.2: Transactional Email Notifications
**Objective:** When a user uploads a 50-page contract and navigates away, send an email when the analysis completes.

**Implementation:**
- Integrate **Resend** or **SendGrid** in `backend/app/services/email_service.py`.
- Triggered inside `JobWorker._complete_job`:
  - Subject: `Your TraceClause AI Audit is Ready: [file_name]`
  - Body: Risk score breakdown, link to open the contract in SplitView, and link to download the native `.docx` redline report.

---

### Task 3.3: Production Telemetry & Observability
- Add **Sentry** for automated backend and frontend exception capturing:
  ```python
  import sentry_sdk
  sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
  ```
- Configure Cloudflare Web Application Firewall (WAF) in front of Vercel and Render to block DDoS and rate-limit abusive IPs.

---

## Verification & Load Testing Checklist

Before opening registration to paying public users, execute the following validation suite:

| Test Case | Tool | Target Metric | Pass Criteria |
| :--- | :--- | :--- | :--- |
| **Unit & Integration Suite** | `pytest` | 32/32 tests passing | 100% green in `< 1.0s` |
| **Concurrent PDF Ingestion** | Locust / k6 | 50 concurrent uploads of 15-page PDFs | 0% failed, response time `< 4.0s` |
| **Durable Queue Concurrency** | Locust / k6 | 100 simultaneous job submissions | All jobs queued in `< 250ms`, worker processes without loss |
| **LLM Rate-Limit Resilience** | Mock 429 generator | Upstream provider returns 429 | System retries 4 times with backoff; 0 canned mock data leaks |
| **Payment Signature Security** | Pytest | Tampered HMAC-SHA256 signature | Returns HTTP 400 `invalid_signature`, zero entitlement grants |
| **Tenant Isolation Security** | Pytest | User A attempts to view User B's job/report | Returns HTTP 404 / 403, 0 data leakage |

---

## Execution Summary: How We Will Roll This Out

1. **Step 1:** Implement Phase 1 immediately (Event loop unblocking in `upload.py` & `analysis.py`, connect `Dropzone.tsx` to `/jobs/submit`, and add LLM retries).
2. **Step 2:** Run the full 32-test Pytest suite to confirm zero regressions.
3. **Step 3:** Deploy to staging, verify live with a 50-page sample contract.
4. **Step 4:** Execute Phase 2 (multi-worker configuration and Supavisor pooling).
5. **Step 5:** Activate Razorpay Live keys and start onboarding customers.

