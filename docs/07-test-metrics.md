# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 Evaluation & Quality Assurance specifies build validation, Next.js Turbopack compilation benchmarks, batched multi-LLM unit tests, Audit Vault retrieval metrics, and dual-vector embedding precision benchmarks.
* **Module Matrix (Version History)**:

| Test Suite Category | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **Node Build Runtime** | Node 20 (Deprecated) | **Node v24.20.0 LTS** (`npm run build` zero-warning Turbopack compiler validation) |
| **LLM Risk Analysis Test**| Single clause per call | **Batched LLM Analysis Test Suite** (50-clause batches, < 2.5s execution, 50x API call reduction) |
| **Vector Embedding Test**| Single 1536-dim test | **Batched Dual Engine 1536-dim Normalization Test Suite** (50-item batches, < 300ms latency) |
| **Audit Vault Persistence**| None | **Audit Vault History Test Suite** (< 200ms report retrieval latency via `/api/v1/contract/my-reports`) |
| **Quota Limits Test** | None | Tier Matrix Test (Free: 3 lifetime audits, Solo: 20/mo, Team: 100/mo pooled with 30-day reset) |
| **Auth Isolation Test**| None | Supabase JWT & RLS Data Isolation Tests + Admin Service Role Key RLS Bypass Tests |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI QUALITY ASSURANCE)

### Component: Quality Assurance & Automated Build Validation Suite

* **Functional Description**: Verifies Next.js 16 build stability, Node 24 runtime compatibility, Python FastAPI batched endpoint responses, Audit Vault persistence, and vector embedding normalization.
* **Technical Specs & Capabilities**:
  - **Frontend Validation**: `npm run build` via Next.js Turbopack compiler on Node `v24.20.0`.
  - **Backend Validation**: `pytest` and FastAPI test client suites.

* **Detailed Input/Output Data Dictionary**:

#### Test Benchmark Performance Matrix

| Operation | Target Response Time | SLA Threshold | Status |
| :--- | :--- | :--- | :--- |
| **Next.js Production Build** | $< 10.0\text{ seconds}$ | $< 20.0\text{ seconds}$ | PASSED (5.6s on Node 24) |
| **Document Text Extraction** | $< 1.2\text{ seconds}$ | $< 3.0\text{ seconds}$ | PASSED |
| **Batched Vector Embedding Generation** | $< 300\text{ ms}$ | $< 1.0\text{ second}$ | PASSED (50-chunk batch, 1536-dim native) |
| **Batched LLM Risk Analysis Audit** | $< 2.5\text{ seconds}$ | $< 5.0\text{ seconds}$ | PASSED (50-clause batch execution) |
| **Audit Vault Report Retrieval** | $< 150\text{ ms}$ | $< 500\text{ ms}$ | PASSED (Supabase `contract_reports` query) |

* **Under-the-Hood Logic & Computations**:
  1. **Node 24 Build Verification**: `npm run build` runs Next.js Turbopack compiler on Node `v24.20.0`, confirming zero deprecation warnings and zero build errors.
  2. **Batched LLM JSON Parsing Test**: Validates that `_extract_json_array` correctly parses JSON arrays surrounded by markdown code fences or arbitrary conversational prose across OpenAI `gpt-4o`, Gemini `gemini-1.5-pro`, and Claude `claude-3-5-sonnet`.
  3. **1536-Dim Vector Dimension Test**: Asserts that both OpenAI `text-embedding-3-small` and Gemini `gemini-embedding-001` with `output_dimensionality=1536` output float arrays of exact length 1536 without zero-padding.
  4. **30-Day Quota Reset Testing**: Tests 30-day auto-reset logic in `QuotaService` by simulating timestamps past `last_quota_reset + timedelta(days=30)`.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ERR_BUILD_FAIL` | 500 | Next.js Compiler | TypeScript type check error | `Build compilation failed` | Internal Server Error | `npm run build` CI guard |
| `ERR_DIM_PADDING` | 400 | Vector Engine | Vector float length != 1536 | `Vector dimensions must equal 1536` | Bad Request | Zero-padding assertion guard |
| `ERR_QUOTA_TEST_FAIL`| 429 | Quota Service | Free audit count >= 3 | `Free trial limit reached (3/3 contracts)` | Too Many Requests | HTTP 429 assertion guard |
