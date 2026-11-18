# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 is designed to prevent legal data loss, handle unexpected API timeouts, manage rate limits, recover from malformed batched LLM responses gracefully without system crashes, and bypass RLS constraints safely using Admin Service Role Keys.
* **Module Matrix (Version History)**:

| Failure & Resilience Category | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **API Key Missing** | Unhandled System Crash (`500`) | Smart Mock Fallback Generator (0% downtime) |
| **Embedding Engine Fail** | Crash on DB query | Context-Window RAG Fallback |
| **Malformed LLM JSON** | Uncaught `json.loads` error | Regex array extraction (`_extract_json_array` matching `r'\[\s*\{.*\}\s*\]'`) + Index-position mapping + Per-clause mock fallback loop |
| **Database RLS Insert Block**| Failed silent insert | Admin Service Role Key (`SUPABASE_SERVICE_ROLE_KEY`) bypass pattern in `UserIsolationService` & `QuotaService` |
| **Account Deletion Safety**| Direct single-click delete | Mandatory typing verification (`DELETE MY ACCOUNT`) |
| **File Disk Leaks** | Temporary files left on disk | Guaranteed RAM extraction + `finally: os.remove()` |
| **Quota Overrun** | Uncapped | Strict HTTP 429 exceptions (3/3 Free lifetime limit, Solo 20/mo, Team 100/mo pooled workspace limit) |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI RESILIENCE & ERROR HANDLING)

### Component: Fault Tolerance & Failure Mitigation Registry

* **Functional Description**: Detects runtime anomalies (missing API keys, malformed JSON responses, database connection drops, quota limits, RLS restrictions) and executes self-healing recovery strategies.
* **Technical Specs & Capabilities**:
  - **Supported Failover Modes**: Automatic LLM provider failover, Batched LLM regex extraction fallback, Mock Redline fallback, Context-Window RAG fallback, 1536-dim vector padding.
  - **Admin Key RLS Bypass**: `get_db_client()` and `get_supabase_client()` attempt `SUPABASE_SERVICE_ROLE_KEY` authorization first before public `SUPABASE_KEY` fallback, ensuring quota counters and Audit Vault reports save without RLS exceptions.
  - **Account Deletion Safety**: Strictly requires typing `"DELETE MY ACCOUNT"` in front-end text box.

* **Detailed Input/Output Data Dictionary**:

#### Error Recovery Event Payload
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `error_type` | `string` | Classification of error | `KEY_MISSING`, `QUOTA_EXCEEDED`, `JSON_DECODE_ERR`, `RLS_BLOCK` |
| `recovery_action` | `string` | Strategy executed | `FALLBACK_TO_MOCK`, `RAM_PURGE`, `SERVICE_ROLE_BYPASS`, `429_RAISED` |

* **Under-the-Hood Logic & Computations**:
  1. **Multi-LLM Key Auto-Detection Fallback**: If no API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`) exist in `.env`, `LLMAnalyzer` automatically returns structured mock redlines so the UI operates 100% smoothly during offline testing.
  2. **Batched LLM Regex JSON Fallback**: If a model returns extra conversational text or markdown code fences surrounding JSON arrays, `_extract_json_array` strips code blocks and applies regex pattern `r'\[\s*\{.*\}\s*\]'`. If JSON parsing fails entirely, `_review_batch` falls back to `_mock_analysis` per clause without throwing a server 500 error.
  3. **Context-Window RAG Fallback**: If vector embeddings cannot be generated, `RAGService` passes extracted text directly into the LLM prompt context window.
  4. **Zero File Storage Cleanup**: Binary contract uploads are parsed inside RAM (`tempfile.NamedTemporaryFile`). Cleanup is enforced via `finally:` block `os.remove(temp_path)` to ensure 0 Bytes rest on disk.
  5. **Admin Service Role Key DB Protection**: `UserIsolationService` & `QuotaService` utilize `SUPABASE_SERVICE_ROLE_KEY` to bypass Supabase client Row-Level Security policies, guaranteeing profile quota creation, 30-day reset, and audit report persistence.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ERR_NO_LLM_KEY` | 200 | LLM Analyzer | No LLM API key present | None | OK (Mock Fallback) | Smart mock fallback generator |
| `ERR_QUOTA_EXCEEDED`| 429 | Quota Service | Free >= 3 or Monthly >= limit | `Free trial limit reached (3/3 contracts)...` | Too Many Requests | HTTP 429 exception |
| `ERR_JSON_MALFORMED`| 200 | LLM Analyzer | LLM response lacks valid JSON array | None (Self-Healed) | OK (Self-Healed) | Regex `r'\[\s*\{.*\}\s*\]'` extraction + per-clause fallback |
| `ERR_RLS_BLOCK` | 200 | DB Client | Public anon key lacks RLS write rights | None (Bypassed) | OK (Self-Healed) | `SUPABASE_SERVICE_ROLE_KEY` admin client fallback |
| `ERR_DELETE_MISMATCH`| 400 | Settings Modal | Confirmation input != `DELETE MY ACCOUNT` | `Type "DELETE MY ACCOUNT" to confirm` | Bad Request | Frontend form validation |
| `ERR_FILE_PURGE` | 500 | Ingestion Engine | Disk remove failure | `Temp file purge failed` | Internal Server Error | `try...finally: os.remove()` |
