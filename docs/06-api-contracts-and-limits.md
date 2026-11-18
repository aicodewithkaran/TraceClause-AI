# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 API Contract & Governance specifies all REST endpoints, request/response payload definitions, 50-item batching limits, live quota tracking metrics, and subscription rate-limiting policies.
* **Module Matrix (Version History)**:

| API & Governance Feature | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **Auth Headers & Guard** | Unauthenticated | Mandatory Supabase Bearer Token + `require_feature` Middleware Guard + Admin Service Role Key RLS Bypass |
| **Analysis Endpoint** | `/api/v1/analysis` | `POST /api/v1/contract/analyze` (Batched LLM inference, 50 clauses/call) |
| **Audit Vault Endpoint**| None | `GET /api/v1/contract/my-reports` (Audit Vault History) |
| **Word Redline Export** | None | `GET /api/v1/contract/{report_id}/export-docx` (Solo & Team tiers) |
| **Workspace Management** | None | `/api/v1/workspaces/` (Team tier only) |
| **Quota Matrix** | 2 Total Audits | Live Tiered Matrix (Free: 3 lifetime audits, Solo: 20/mo, Team: 100/mo pooled) |
| **Batching Governance** | Single clause per call | **Batched Pipeline**: 50 clauses per LLM API call & 50 texts per embedding API call |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI API CONTRACTS)

### Component: REST API Endpoint & Token Governance Matrix

* **Functional Description**: Governs all incoming HTTP endpoints, payload validations, 50-item request batching, feature entitlement authorization middleware, live quota limits, and multi-provider token allocations.
* **Technical Specs & Capabilities**:
  - **Base API URL**: `/api/v1`
  - **Auth Scheme**: HTTP Bearer Header (`Authorization: Bearer <supabase_access_token>`).
  - **Authorization Middleware**: `require_feature(feature_name)` enforces tier permissions and returns `HTTP 403 Forbidden` if user subscription is insufficient.
  - **Batching Governance**: Limits LLM inference and embedding generation to groups of up to 50 clauses (`BATCH_SIZE = 50`).

* **Detailed Input/Output Data Dictionary**:

#### REST Endpoint Reference

| Method | Endpoint Route | Request Body | Success Response | Error Codes |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/contract/analyze` | `{"file_name": "...", "extracted_text": "..."}` | `ContractAnalysisResponse` | `400`, `401`, `429`, `500` |
| `GET` | `/api/v1/contract/my-reports` | None | `List[ContractReport]` | `401`, `500` |
| `GET` | `/api/v1/contract/{report_id}/export-docx` | None | `StreamingResponse (.docx)` | `401`, `403`, `404`, `500` |
| `POST` | `/api/v1/rag/chat` | `{"contract_text": "...", "question": "..."}` | `{"answer": "...", "citations": [...]}` | `401`, `403`, `500` |
| `GET` | `/api/v1/workspaces/` | None | `{"workspaces": [...]}` | `401`, `403`, `500` |
| `POST` | `/api/v1/workspaces/` | `{"name": "..."}` | `{"status": "success", "workspace": {...}}` | `401`, `403`, `500` |

#### Contract Analysis Response Payload Schema
```json
{
  "file_name": "Vendor_Agreement_2026.pdf",
  "extracted_text": "...",
  "summary": {
    "total_clauses": 14,
    "high_risks": 2,
    "medium_risks": 5,
    "low_risks": 7,
    "overall_risk_score": "HIGH RISK"
  },
  "clauses": [
    {
      "clause_number": 1,
      "clause_name": "Section 14: Indemnification",
      "original_text": "...",
      "risk_level": "High",
      "risk_explanation": "Uncapped customer indemnification...",
      "suggested_counter_language": "Modify section to mutual capped indemnification...",
      "category": "Indemnity"
    }
  ]
}
```

* **Under-the-Hood Logic & Computations**:
  1. **Feature Guard**: `require_feature` checks user's `subscription_tier` against allowed capability sets (`rag_interactive_chat`, `docx_export`, `workspace_management`, `custom_playbook_rules`).
  2. **Live Quota Check**: Checks `lifetime_free_audits_used` for Free users (hard limit 3), and `monthly_quota_used` for Solo (20/mo) and Team (100/mo pooled). Throws `429` if exceeded.
  3. **Batched LLM Execution**: Partitions extracted clauses into batches of 50 (`BATCH_SIZE = 50`) and executes a single LLM API call per batch across auto-selected provider (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`).
  4. **Audit Vault Storage**: Saves output JSON into `public.contract_reports` via `UserIsolationService.save_user_report`.
  5. **Native 1536 Vector Storage**: Requests native 1536-dim embeddings in 50-item batches via `gemini-embedding-001` or OpenAI `text-embedding-3-small` and saves to `public.contract_embeddings`.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ERR_UNAUTHORIZED` | 401 | Security Middleware | Missing Bearer token | `Not authenticated` | Unauthorized | Supabase JWT token guard |
| `ERR_FORBIDDEN_FEATURE`| 403 | Auth Middleware | Tier lacks feature permission | `Access denied: '{feature}' requires Solo or Team plan.` | Forbidden | FastAPI `Depends(require_feature(...))` |
| `ERR_QUOTA_EXCEEDED`| 429 | Quota Service | Quota limit exceeded | `Free trial limit reached (3/3 contracts). Please upgrade to Solo ($79) or Team ($299).` | Too Many Requests | HTTP 429 exception |
| `ERR_EMPTY_PAYLOAD` | 400 | Analysis Endpoint | Extracted text empty | `Extracted contract text cannot be empty.` | Bad Request | Guard clause validation |
