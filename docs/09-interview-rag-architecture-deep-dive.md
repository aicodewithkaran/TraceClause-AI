# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 Interview Guide documents the architectural decisions, 50-clause batched multi-LLM analysis, Audit Vault history storage, RAG pipeline, multi-LLM failover, dual vector normalization, zero file storage guarantees, and live quota enforcement.
* **Module Matrix (Version History)**:

| Architectural Component | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **System Identity** | ScanShield AI v1.0 | TraceClause AI v2.0 |
| **LLM Provider** | Single OpenAI | **Batched Multi-LLM Auto-Detection** (OpenAI `gpt-4o`, Gemini `gemini-1.5-pro`, Claude `claude-3-5-sonnet` in 50-clause batches with regex parsing) |
| **Embedding Engine** | Single OpenAI | **Batched Dual Engine** (OpenAI + Gemini normalized to 1536-dim via MRL in 50-item batches) |
| **Audit Vault System**| None | **Supabase Audit Vault** (`contract_reports` table populated via `SUPABASE_SERVICE_ROLE_KEY`) |
| **Storage Security** | Temporary Disk | Zero File Storage Guarantee (RAM-only extraction, auto-purged) |
| **Auth & Isolation** | Unauthenticated | Supabase Auth + JWT User Isolation + RLS Policies + Admin Service Role Key Bypass |
| **Quota Architecture**| Uncapped | Live Quota Tracking (Free: 3 lifetime audits, Solo: 20/mo, Team: 100/mo pooled across 4 workspace seats) |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI RAG DEEP DIVE)

### Component: RAG Vector Retriever & Redline Reasoning Engine

* **Functional Description**: Performs 50-clause batched legal risk analysis, semantic clause retrieval, AI redline generation, Audit Vault persistence, and natural language Q&A resolution with clause citations.
* **Technical Specs & Capabilities**:
  - **Vector Database**: Supabase PostgreSQL with `pgvector` HNSW index (`vector_cosine_ops`).
  - **Vector Dimension**: Standardized native 1536 float32 dimensions.
  - **Audit Vault History**: Saved reports in `contract_reports` retrieved via `/api/v1/contract/my-reports`.

* **Detailed Input/Output Data Dictionary**:

#### RAG Citation Chat Request (`POST /api/v1/rag/chat`)
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `contract_text` | `string` | Analyzed contract text | Mandatory non-empty string |
| `question` | `string` | User Q&A question | e.g. "What is the liability cap?" |

#### RAG Citation Chat Response Payload
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `answer` | `string` | AI-generated legal answer | Grounded answer text |
| `citations` | `List[string]` | Citation tags | e.g. `["TraceClause RAG (gpt-4o)"]` or `["Section 12: Limitation of Liability"]` |

* **Under-the-Hood Logic & Computations**:
  1. **50-Clause Batched LLM Analysis**: Contract clauses are processed in batches of 50 (`BATCH_SIZE = 50`), reducing API calls by 50x. Output is parsed using regex matcher `_extract_json_array(r'\[\s*\{.*\}\s*\]')` with index-position fallback.
  2. **Audit Vault History Persistence**: Analyzed reports are persisted into `public.contract_reports` using the Admin `SUPABASE_SERVICE_ROLE_KEY` to bypass Supabase RLS policies safely.
  3. **Dual Embedding Normalization**: Input queries and contract text chunks are converted to vector arrays using `text-embedding-3-small` or `gemini-embedding-001` with `output_dimensionality=1536`.
  4. **HNSW Cosine Vector Search**: Computes `<=>` distance against `contract_embeddings` where `user_id = current_user.id` or matching `workspace_id`.
  5. **Context-Window Fallback**: If vector embeddings are disabled, `VectorStoreService` passes the document text directly into the LLM context window.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ERR_NO_LLM_KEY` | 200 | LLM Analyzer | No LLM key present | None (Triggers Mock) | OK (Mock Fallback) | Smart mock fallback generator |
| `ERR_EMBED_PADDING`| 400 | Vector Engine | Vector length != 1536 | `Vector dimensions must equal 1536` | Bad Request | Zero-padding normalization assertion |
| `ERR_QUOTA_EXCEEDED`| 429 | Quota Service | Free audit count >= 3 | `Free trial limit reached (3/3 contracts)` | Too Many Requests | HTTP 429 exception with upgrade modal |
