# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 Architecture, Environment & Database Master Reference provides a definitive roadmap of all environment variables, Supabase PostgreSQL schemas, Audit Vault storage, JWT authentication flows, RAM-only file lifecycles, and completed product roadmap milestones.
* **Module Matrix (Version History)**:

| System Architecture Domain | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **System Branding** | ScanShield AI v1.0 | TraceClause AI v2.0 |
| **Environment Files** | Single `.env` file | Decoupled `backend/.env` & `frontend/.env.local` |
| **Database Architecture** | Local In-Memory Dict | Supabase PostgreSQL (`profiles`, `workspaces`, `workspace_members`, `contract_reports`, `contract_embeddings` + `pgvector` HNSW) |
| **Auth & Authorization** | None | Supabase Auth + JWT Verification + RLS Policies + Admin Service Role Key Bypass + Inline `AuthModal.tsx` |
| **Analysis Pipeline** | Monolithic single clause | **Batched LLM Pipeline** (50 clauses per call across OpenAI, Gemini, and Claude) |
| **Audit Vault Storage** | None | Persistent Audit Vault History (`contract_reports`) |
| **Payment Integration** | Single Stripe | Dual Gateways: Stripe (USD) & Razorpay (INR/UPI/Cards) + Razorpay Payment Link Integration |
| **File Lifecycle Policy** | Local disk retention | Zero File Storage Guarantee (RAM-only extraction) |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI MASTER ROADMAP & ENVIRONMENT CONFIG)

### Component: System Configuration, Storage Policy & Product Roadmap

* **Functional Description**: Governs server and client environment variables, database table relations, multi-seat workspace management, Audit Vault history storage, zero-storage privacy policies, and subscription tier rules.
* **Technical Specs & Capabilities**:
  - **Backend Settings**: Managed via `pydantic-settings` in `app/core/config.py`.
  - **Frontend Environment**: Bundled via Next.js (`NEXT_PUBLIC_` prefixed variables).

* **Detailed Input/Output Data Dictionary**:

#### Environment Variable Master Dictionary

#### Backend (`backend/.env`)
| Variable Name | Data Type | Description | Security / Scope |
| :--- | :--- | :--- | :--- |
| `PROJECT_NAME` | `string` | FastAPI service name | Server-only (`"TraceClause AI"`) |
| `SUPABASE_URL` | `string` | Supabase API endpoint | Server & Client |
| `SUPABASE_KEY` | `string` | Supabase Public Anon Key | Server & Client |
| `SUPABASE_SERVICE_ROLE_KEY` | `string` | Supabase Admin Secret Key (**RLS Bypass**) | **Server-Only (Secret)** |
| `OPENAI_API_KEY` | `string` | OpenAI API key | **Server-Only (Secret)** |
| `GEMINI_API_KEY` | `string` | Google AI Studio API key | **Server-Only (Secret)** |
| `ANTHROPIC_API_KEY` | `string` | Anthropic API key | **Server-Only (Secret)** |

#### Frontend (`frontend/.env.local`)
| Variable Name | Data Type | Description | Security / Scope |
| :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `string` | FastAPI backend URL | Public Client (`"http://localhost:8000/api/v1"`) |
| `NEXT_PUBLIC_SUPABASE_URL` | `string` | Supabase API URL | Public Client |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `string` | Supabase Public Key | Public Client |
| `NEXT_PUBLIC_RAZORPAY_KEY_ID` | `string` | Razorpay Client Key | Public Client |

* **Under-the-Hood Logic & Computations**:
  1. **RAM-Only File Parsing**: `upload_document` endpoint creates a `tempfile.NamedTemporaryFile`. Extraction happens in RAM, and `finally: os.remove(temp_path)` guarantees zero file retention on disk.
  2. **Batched LLM & Embedding Engine**: Processes clauses and embeddings in batches of 50 (`BATCH_SIZE = 50`), reducing latency by up to 50x.
  3. **Audit Vault History System**: Saves analyzed contract reports into `public.contract_reports` using the Admin `SUPABASE_SERVICE_ROLE_KEY` to bypass Supabase RLS restrictions safely.
  4. **Live Tiered Quota & Workspace Matrix**: Checks user tier in Supabase `profiles` (Free: 3 lifetime total audits hard stop; Solo: 20/mo; Team: 100/mo pooled across 4 workspace seats with 30-day auto reset).

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ERR_ENV_VALIDATION`| 500 | Config Engine | Missing required env variable | `Field required` | Internal Server Error | `pydantic-settings` validation |
| `ERR_FILE_PURGE` | 500 | Ingestion Engine | Disk remove failure | `Temp file purge failed` | Internal Server Error | `try...finally: os.remove()` |
| `ERR_QUOTA_EXCEEDED`| 429 | Quota Service | Free audit count >= 3 | `Free trial limit reached (3/3 contracts)` | Too Many Requests | HTTP 429 exception with upgrade prompt |
