# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 is a commercial contract risk analyzer, interactive RAG platform, and Audit Vault system. It parses PDF/Word contracts in RAM, extracts structured legal clauses, generates AI redline counter-language via batched LLM analysis, tracks live subscription quotas, stores vector embeddings in Supabase (`pgvector`), and persists user audit history.
* **Module Matrix (Version History)**:

| Architectural Component | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **Branding & Identity** | ScanShield AI v1.0 | TraceClause AI v2.0 |
| **Pipeline Engine** | Monolithic text extraction | RAM-only extraction, semantic chunking & **Batched LLM Clause Risk Analysis** (`BATCH_SIZE = 50`) |
| **LLM Provider Routing**| Hardcoded OpenAI API | Multi-LLM Auto-Detection (OpenAI `gpt-4o`, Gemini `gemini-1.5-pro`, Anthropic `claude-3-5-sonnet`) with regex array parsing (`_extract_json_array`) |
| **Embedding Engine** | OpenAI `text-embedding-ada-002` | Dual Engine: OpenAI (`text-embedding-3-small`) & Gemini (`gemini-embedding-001` with `output_dimensionality=1536`) with batched embedding generation |
| **Vector Normalization**| Un-normalized 1536-dim | Native 1536-dim vector MRL embedding (Zero-padding eliminated, assertion enforced) |
| **Export Engine** | JSON preview only | Native `.docx` Word Redline Exporter (`python-docx` with red strikethrough & green underline) |
| **File Storage & Vault**| Temporary Disk Retention | Zero File Storage Guarantee (RAM extraction, auto-purged) + Supabase **Audit Vault History** (`contract_reports`) |
| **Security & Auth** | Global unauthenticated access | Supabase Auth + JWT User Isolation + RLS + Admin Service Role Key Bypass + Inline `AuthModal.tsx` |
| **Quota & Workspace Matrix** | Uncapped | Live Quota Tracking: Free (3 lifetime audits), Solo (20/mo), Team (100/mo pooled + 4 seats workspace) |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI LOW-LEVEL WIRING)

### Component: Ingestion, Batched Analysis & Multi-LLM Routing Pipeline

* **Functional Description**: Handles incoming contract file upload, RAM-only text extraction, hierarchical clause splitting, 50-clause batched multi-provider LLM risk analysis, dual-provider 1536-dim batched vector embedding generation, Audit Vault report persistence, and native `.docx` redline report exports.
* **Technical Specs & Capabilities**:
  - **Supported Formats**: PDF (`.pdf`), Word (`.docx`), Plain Text (`.txt`). Size limit: 25 MB per document.
  - **RAM-Only Processing**: Temporary files created via `tempfile.NamedTemporaryFile` and deleted immediately inside `finally:` blocks.
  - **Batched LLM Risk Analysis**: `LLMAnalyzer.analyze_clauses` batches clauses into groups of up to 50 (`BATCH_SIZE = 50`), executing a single LLM API call per batch to reduce LLM calls by 50x and dramatically lower overall latency.
  - **Robust JSON Array Parser**: `_extract_json_array` employs regex matching `r'\[\s*\{.*\}\s*\]'` to safely parse JSON arrays across OpenAI, Gemini (`genai.Client`), and Anthropic (`Anthropic`), with index-position fallback.
  - **Batched 1536-Dim Embedding Generation**: Requests 1536 native dimensions in batches of up to 50 items via `VectorStoreService.generate_embeddings_batch`.
  - **Audit Vault Persistence**: `UserIsolationService.save_user_report` uses the Admin `SUPABASE_SERVICE_ROLE_KEY` to bypass RLS restrictions safely when writing audit metadata and JSON redlines to `public.contract_reports`.
  - **Native `.docx` Redline Export**: `DocxExporter` generates Microsoft Word `.docx` documents featuring strikethrough red original text for modified clauses, green underlined counter-language recommendations, and inline callout boxes detailing risk rationale.

* **Detailed Input/Output Data Dictionary**:

#### Request Payload (`POST /api/v1/contract/analyze`)
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `file_name` | `string` | Original name of uploaded contract | Mandatory string |
| `extracted_text` | `string` | Raw extracted document text | Mandatory non-empty string |

#### Audit History Request (`GET /api/v1/contract/my-reports`)
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `Authorization` | `string` | HTTP Bearer Token | `Bearer <supabase_access_token>` |

#### Response Payload (`ContractAnalysisResponse`)
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `file_name` | `string` | Contract file name | Non-empty string |
| `summary.overall_risk_score` | `string` | Executive risk score | `HIGH RISK`, `MEDIUM RISK`, `LOW RISK` |
| `summary.total_clauses` | `integer` | Count of clauses parsed | Non-negative integer |
| `summary.high_risks` | `integer` | Count of high risk clauses | Non-negative integer |
| `summary.medium_risks` | `integer` | Count of medium risk clauses | Non-negative integer |
| `summary.low_risks` | `integer` | Count of low risk clauses | Non-negative integer |
| `clauses[].clause_number` | `integer` | Clause index | Sequential integer |
| `clauses[].clause_name` | `string` | Identified clause title | e.g. "Section 14: Indemnification" |
| `clauses[].risk_level` | `string` | Clause risk rating | `HIGH`, `MEDIUM`, `LOW` |
| `clauses[].risk_explanation` | `string` | Plain-english risk summary | Non-empty string |
| `clauses[].suggested_counter_language` | `string` | AI-generated redline fix | Recommended safer legal language |

* **Under-the-Hood Logic & Computations**:
  1. **Upload & Ingestion**: FastAPI endpoint `/api/v1/contract/analyze` receives document text.
  2. **Live Quota & Tier Authorization**: `QuotaService.check_and_increment_quota(user_id)` checks user audit limits (Free: 3 lifetime audits hard stop; Solo: 20/mo; Team: 100/mo pooled across workspace with 30-day auto reset).
  3. **Semantic Chunking**: `ChunkingEngine.split_into_clauses(text)` splits contract text by regex patterns matching `Article`, `Section`, and numerical headings.
  4. **Batched Multi-LLM Analysis**: `LLMAnalyzer.analyze_clauses` groups clauses into batches of 50. Uses auto-detected key: `OPENAI_API_KEY` (`gpt-4o`) -> `GEMINI_API_KEY` (`gemini-1.5-pro`) -> `ANTHROPIC_API_KEY` (`claude-3-5-sonnet`) -> `Mock Fallback`.
  5. **Audit Vault Storage**: `UserIsolationService.save_user_report(user_id, file_name, overall_score, summary_data, clauses_data)` writes contract results to `public.contract_reports`.
  6. **Batched 1536 Embedding Generation**: `VectorStoreService.generate_embeddings_batch` embeds chunks in batches using `OPENAI_EMBEDDING_MODEL` or `gemini-embedding-001` with `output_dimensionality=1536`. Enforces assertion `len(embedding) == 1536`.
  7. **Redline `.docx` Exporter**: `GET /api/v1/contract/{report_id}/export-docx` calls `DocxExporter.generate_redline_docx(report_data)`, building native Word documents with red strikethrough original clause text, green underlined counter-language, and shaded callout boxes, guarded by `require_feature("docx_export")`.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `EMPTY_TEXT` | 400 | Ingestion Engine | `len(extracted_text.strip()) == 0` | `Extracted contract text cannot be empty.` | Bad Request | Guard clause in `analysis.py` |
| `FORBIDDEN_FEATURE` | 403 | Auth Middleware | Feature not allowed in tier | `Access denied: '{feature_name}' requires an active Solo or Team plan.` | Forbidden | FastAPI `Depends(require_feature(...))` |
| `QUOTA_EXCEEDED` | 429 | Quota Service | Free audits >= 3 or Monthly >= limit | `Free trial limit reached (3/3 contracts). Please upgrade to Solo ($79) or Team ($299).` | Too Many Requests | FastAPI `HTTPException(429)` |
| `LLM_KEY_MISSING`| 200 | LLM Analyzer | No API keys set in `.env` | None (Triggers Mock Fallback) | OK (Mock Response) | Smart mock fallback generator |
| `AUTH_HEADER_MISSING`|401 | Security Middleware | Missing Bearer token | `Not authenticated` | Unauthorized | Supabase JWT verification guard |
| `FILE_TEMP_LEAK` | 500 | Ingestion Engine | Temp file cleanup failure | `Failed to purge temporary file` | Internal Server Error | `try...finally: os.remove()` guard |
