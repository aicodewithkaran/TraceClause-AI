# 11-database-schema-vector-storage-deep-dive.md

# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 is a commercial contract risk analyzer, Audit Vault history viewer, and interactive RAG platform. It parses PDF/Word contracts in RAM, extracts structured legal clauses, generates AI redline counter-language in 50-clause batches, tracks live quotas, persists contract report history in Supabase (`contract_reports`), and stores vector embeddings in Supabase (`pgvector`).
* **Module Matrix (Version History)**:

| Feature / Capability | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **Database Engine** | Local In-Memory Mock Dict | Supabase PostgreSQL + `pgvector` HNSW |
| **Audit Vault Storage** | None | `contract_reports` table for historical audit reports |
| **Multi-Seat Workspaces** | None | `workspaces` & `workspace_members` tables (4 seats on Team plan) |
| **User Data Isolation** | Global / Unauthenticated | Supabase Auth JWT + Row-Level Security (RLS) + Admin Service Role Key Bypass (`SUPABASE_SERVICE_ROLE_KEY`) |
| **Embedding Engine** | Single-Provider OpenAI (1536-dim) | Dual Engine: OpenAI (1536-dim) + Gemini `gemini-embedding-001` (Native 1536-dim via MRL, 50-item batches) |
| **File Storage** | Temporary Disk Retention | Zero File Storage (RAM-only extraction, auto-purged) |
| **Quota Matrix** | Uncapped | Live Tiered Matrix: Free (3 lifetime audits), Solo (20/mo), Team (100/mo pooled with 30-day reset) |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI DATABASE ARCHITECTURE)

### Component: Supabase Relational & Vector Storage Layer

* **Functional Description**: Manages relational user profiles, multi-seat workspaces, workspace membership, Audit Vault contract redline reports, and native 1536-dimensional clause vector embeddings with strict tenant & workspace isolation.
* **Technical Specs & Capabilities**:
  - PostgreSQL 15+ with `pgvector` extension enabled.
  - HNSW Indexing with `vector_cosine_ops` for high-speed similarity search.
  - Maximum payload size per vector: Native 1536 float32 dimensions (6 KB per vector).
  - Admin Service Role Key Authorization: Uses `SUPABASE_SERVICE_ROLE_KEY` to guarantee profile updates, quota counter updates, and report writes bypass RLS restrictions safely.

* **Detailed Input/Output Data Dictionary**:

#### Table: `public.profiles`
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key referencing `auth.users(id)` | Mandatory, `ON DELETE CASCADE` |
| `email` | `TEXT` | User registration email | Mandatory, Valid Email Format |
| `full_name` | `TEXT` | User display name | Mandatory, Non-empty |
| `country` | `TEXT` | User country of operation | Mandatory, ISO / Global standard |
| `profession` | `TEXT` | User professional role | Mandatory |
| `subscription_tier`| `TEXT` | Subscription tier (`free`, `solo`, `team`) | DEFAULT `'free'` |
| `lifetime_free_audits_used`| `INT` | Counter for free tier audits | DEFAULT `0`, hard stop limit at 3 |
| `weekly_quota_used`| `INT` | Counter for legacy weekly tracking | DEFAULT `0` |
| `monthly_quota_used`| `INT` | Counter for paid monthly contract reviews | DEFAULT `0`, 30-day auto reset |
| `last_quota_reset` | `TIMESTAMPTZ` | Timestamp of last 30-day quota reset | DEFAULT `NOW()` |

#### Table: `public.workspaces` (For Team Tier)
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | `gen_random_uuid()` |
| `owner_id` | `UUID` | Foreign Key referencing `profiles(id)` | Mandatory, `ON DELETE CASCADE` |
| `name` | `TEXT` | Workspace name | Mandatory |
| `seat_limit` | `INT` | Seat capacity | Default `4` |

#### Table: `public.workspace_members`
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | `gen_random_uuid()` |
| `workspace_id` | `UUID` | Foreign Key referencing `workspaces(id)` | Mandatory, `ON DELETE CASCADE` |
| `user_id` | `UUID` | Foreign Key referencing `profiles(id)` | Mandatory, `ON DELETE CASCADE` |
| `role` | `TEXT` | Member role (`owner`, `member`) | Default `'member'`, `UNIQUE(workspace_id, user_id)` |

#### Table: `public.contract_reports` (Audit Vault History)
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | `gen_random_uuid()` |
| `user_id` | `UUID` | Foreign Key referencing `profiles(id)` | Mandatory, `ON DELETE CASCADE` |
| `workspace_id` | `UUID` | Foreign Key referencing `workspaces(id)` | Optional, `ON DELETE SET NULL` |
| `file_name` | `TEXT` | Name of analyzed document | Mandatory |
| `overall_risk_score`| `TEXT` | Executive risk summary | `HIGH RISK`, `MEDIUM RISK`, `LOW RISK` |
| `summary_json` | `JSONB` | Clause count breakdown | Valid JSON Object |
| `clauses_json` | `JSONB` | Array of parsed clause redlines | Valid JSON Array |
| `created_at` | `TIMESTAMPTZ` | Creation timestamp | DEFAULT `NOW()` |

#### Table: `public.contract_embeddings`
| Field Name | Data Type | Description | Validation Rules / Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | `gen_random_uuid()` |
| `report_id` | `UUID` | Foreign Key referencing `contract_reports(id)` | Mandatory, `ON DELETE CASCADE` |
| `user_id` | `UUID` | Foreign Key referencing `profiles(id)` | Mandatory, `ON DELETE CASCADE` |
| `workspace_id` | `UUID` | Foreign Key referencing `workspaces(id)` | Optional, `ON DELETE SET NULL` |
| `clause_number` | `INT` | Clause sequential index | Non-negative integer |
| `clause_text` | `TEXT` | Raw text excerpt of clause | Mandatory |
| `embedding` | `vector(1536)`| Native 1536-dim vector embedding | Float array of length 1536 (Assertion enforced) |

* **Under-the-Hood Logic & Computations**:
  1. **User Profile & Workspace Provisioning**: When a user subscribes to Team tier, `PaymentService` creates a `workspaces` record (4 seats) and inserts the owner into `workspace_members`.
  2. **Audit Vault Storage**: `UserIsolationService.save_user_report` inserts summary metadata and redlines into `public.contract_reports` using the Admin `SUPABASE_SERVICE_ROLE_KEY` client to bypass client RLS restrictions safely.
  3. **Native 1536 Vector Generation**: Chunks are embedded in 50-item batches via `gemini-embedding-001` with `output_dimensionality=1536` or OpenAI `text-embedding-3-small`. Vector length assertion `len(embedding) == 1536` ensures dimensional integrity without zero-padding.
  4. **Workspace RLS Sharing**: Row Level Security policies permit workspace members to query reports and vector embeddings associated with their shared `workspace_id`.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `DB_CONN_FAIL` | 500 | Supabase Client | Invalid API Key or URL | `Failed to connect to Supabase database` | Internal Server Error | Client fallback to mock dict |
| `RLS_VIOLATION`| 403 | Supabase Auth | Accessing report of another user/workspace | `Row Level Security policy violation` | Forbidden | JWT `auth.uid()` & workspace validation |
| `VEC_DIM_MISMATCH`|400| Vector Engine | Vector dimension != 1536 | `Expected embedding dimensionality 1536` | Bad Request | MRL output_dimensionality config |
| `QUOTA_EXCEEDED`| 429 | Quota Service | Free audits >= 3 or Monthly >= limit | `Free trial limit reached (3/3 contracts)` | Too Many Requests | HTTP 429 exception with upgrade prompt |
