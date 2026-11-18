# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 Backend is built using Python FastAPI, providing 50-clause batched multi-LLM risk analysis (OpenAI, Gemini, Anthropic), batched dual embedding vector generation with native 1536-dim normalization, Supabase JWT user isolation, Audit Vault report history, and live tiered subscription quota enforcement.
* **Module Matrix (Version History)**:

| Backend Component | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **Framework & Server** | FastAPI (uvicorn) | FastAPI v0.115+ (uvicorn, port 8000, Python 3.11+) |
| **LLM Provider Service** | Single-provider OpenAI | **Batched Multi-LLM Analysis** (`llm_analyzer.py` supporting GPT-4o, Gemini 1.5 Pro, Claude 3.5 Sonnet in 50-clause batches with regex array parsing) |
| **Embedding Engine** | Single-provider OpenAI | **Batched Dual Engine** (`vector_store.py` supporting OpenAI & Gemini `gemini-embedding-001` with native 1536-dim via MRL in 50-item batches) |
| **Audit Vault Service** | None | `UserIsolationService` (`user_isolation.py` saving and retrieving contract reports via `SUPABASE_SERVICE_ROLE_KEY`) |
| **Export Service** | JSON preview only | Native `.docx` Exporter (`docx_exporter.py` with red strikethrough & green underline) |
| **Security & Auth** | Unauthenticated | Supabase Auth JWT Verification (`security.py`) + Feature Entitlement Middleware (`dependencies.py` `require_feature`) + Admin Service Role Key DB access |
| **Quota Matrix** | Uncapped | Live Tiered Quota Matrix (`quota_service.py`: Free 3 lifetime audits, Solo 20/mo, Team 100/mo pooled with 30-day reset) |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI BACKEND ARCHITECTURE)

### Component: FastAPI Core Server & Routing Engine

* **Functional Description**: Coordinates document analysis, batched LLM risk inference, batched vector embeddings, RAG query searches, Audit Vault report storage and retrieval, tier-gated feature authorization, user & workspace quota enforcement, native `.docx` redline exports, multi-seat workspace management, and multi-provider failover.
* **Technical Specs & Capabilities**:
  - **Environment Configuration**: `pydantic-settings` via `app/core/config.py`.
  - **Auto-Detection Logic**: `LLM_PROVIDER` and `EMBEDDING_PROVIDER` default to auto-detecting active keys in `.env`.
  - **Feature Gate Guard**: `require_feature(feature_name)` dependency enforces tier permissions (`free`, `solo`, `team`) and raises HTTP 403 Forbidden for unauthorized capabilities.
  - **Admin Service Role Key DB Access**: `get_db_client()` in `user_isolation.py` and `QuotaService.get_supabase_client()` attempt `SUPABASE_SERVICE_ROLE_KEY` first, guaranteeing profile updates and report saves bypass Supabase RLS restrictions safely.

* **Detailed Input/Output Data Dictionary**:

#### Analysis Request Schema (`ContractAnalysisResponse`)
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `file_name` | `string` | Contract file name | Non-empty string |
| `extracted_text` | `string` | Extracted contract text | Non-empty string |
| `summary.overall_risk_score` | `string` | Executive risk score | `HIGH RISK`, `MEDIUM RISK`, `LOW RISK` |
| `summary.total_clauses` | `integer` | Count of clauses parsed | Non-negative integer |
| `summary.high_risks` | `integer` | High risk clause count | Non-negative integer |
| `summary.medium_risks` | `integer` | Medium risk clause count | Non-negative integer |
| `summary.low_risks` | `integer` | Low risk clause count | Non-negative integer |
| `clauses[].clause_number` | `integer` | Clause sequential index | Non-negative integer |
| `clauses[].clause_name` | `string` | Clause title | e.g. "Section 14: Indemnification" |
| `clauses[].risk_level` | `string` | Risk rating | `HIGH`, `MEDIUM`, `LOW` |
| `clauses[].risk_explanation` | `string` | Plain-english risk summary | Non-empty string |
| `clauses[].suggested_counter_language` | `string` | Suggested redline fix | Recommended legal text |
| `clauses[].category` | `string` | Legal classification | `Indemnity`, `Liability`, `Termination`, `IP`, `General` |

* **Under-the-Hood Logic & Computations**:
  1. **Live Quota & Tier Verification**: `QuotaService.check_and_increment_quota(user_id)` checks `lifetime_free_audits_used` for Free users (hard limit at 3), and `monthly_quota_used` for Solo (20/mo) and Team (100/mo pooled across workspace members). Checks 30-day reset logic (`last_quota_reset`).
  2. **Feature Entitlement Middleware (`require_feature`)**:
     - `free`: `{"risk_score_clause_extraction", "plain_english_explanations"}`
     - `solo`: `{"risk_score_clause_extraction", "plain_english_explanations", "ai_redline_generation", "docx_export", "rag_interactive_chat"}`
     - `team`: `{"risk_score_clause_extraction", "plain_english_explanations", "ai_redline_generation", "docx_export", "rag_interactive_chat", "workspace_management", "custom_playbook_rules"}`
  3. **Batched Multi-LLM Analysis**: `LLMAnalyzer.analyze_clauses` partitions extracted clauses into batches of 50 (`BATCH_SIZE = 50`). Generates structured prompt with JSON schema and parses response via regex matcher `_extract_json_array(r'\[\s*\{.*\}\s*\]')`. Auto-detects `OPENAI_API_KEY` (`gpt-4o`), `GEMINI_API_KEY` (`gemini-1.5-pro`), or `ANTHROPIC_API_KEY` (`claude-3-5-sonnet`).
  4. **Audit Vault History Storage**: `UserIsolationService.save_user_report` saves the contract metadata and redline JSON array into `public.contract_reports`, associated with `user_id`. `UserIsolationService.get_user_reports` fetches history for `/api/v1/contract/my-reports`.
  5. **Batched 1536-Dim Embedding Generation**: `VectorStoreService.generate_embeddings_batch` embeds chunks in 50-item batches using `OPENAI_EMBEDDING_MODEL` (`text-embedding-3-small`) or `gemini-embedding-001` with `output_dimensionality=1536`, asserting `len(embedding) == 1536`.
  6. **Redline `.docx` Exporter**: `DocxExporter.generate_redline_docx(report_data)` builds Microsoft Word documents containing original clauses in strikethrough red font, counter-language recommendations in green underline font, and risk rationale callout boxes.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `FORBIDDEN_FEATURE` | 403 | Auth Guard | Feature not permitted in user tier | `Access denied: '{feature}' requires Solo or Team plan.` | Forbidden | FastAPI `Depends(require_feature(...))` |
| `QUOTA_EXCEEDED` | 429 | Quota Service | Free audits >= 3 or Monthly >= limit | `Free trial limit reached (3/3 contracts)...` | Too Many Requests | FastAPI `HTTPException(429)` |
| `LLM_KEY_MISSING`| 200 | LLM Analyzer | No API keys set in `.env` | None (Triggers Mock Fallback) | OK (Mock Response) | Smart mock fallback generator |
| `AUTH_HEADER_MISSING`|401 | Security Middleware | Missing Bearer token | `Not authenticated` | Unauthorized | Supabase JWT verification guard |
