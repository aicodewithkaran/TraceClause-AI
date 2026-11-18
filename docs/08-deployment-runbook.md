# SECTION 1: SYSTEM OVERVIEW & ARCHITECTURAL EVOLUTION
* **High-Level Purpose**: TraceClause AI v2 Production Deployment Runbook details the step-by-step release process for deploying the Next.js frontend to Vercel/Node 24 and the FastAPI backend to Render/Railway with Supabase integration, Admin Service Role Key configuration, and Razorpay payment link setup.
* **Module Matrix (Version History)**:

| Deployment Category | Version 1.0 (ScanShield Legacy) | Version 2.0 (TraceClause AI Current) |
| :--- | :--- | :--- |
| **Frontend Platform** | Vercel (Node 20) | Vercel / Next.js 16 (**Node 24 LTS**) |
| **Backend Platform** | Railway / Render | Railway / Render (Python 3.11+ Virtualenv, FastAPI v0.115+) |
| **Database Migration**| Local script | Supabase SQL Editor execution (`supabase_schema.sql` provisioning `profiles`, `workspaces`, `contract_reports`, `contract_embeddings`) |
| **Admin Key Security** | None | `SUPABASE_SERVICE_ROLE_KEY` configured in backend environment for RLS bypass |
| **Payment Environment**| None | `NEXT_PUBLIC_RAZORPAY_KEY_ID` configured in frontend environment |
| **Environment Check** | Manual `.env` | Complete `.env.example` templates for Frontend & Backend |

---

# SECTION 2: DEEP DIVE - MODULE VERSION 2.0 (TRACECLAUSE AI DEPLOYMENT RUNBOOK)

### Component: Production Deployment & Database Provisioning Engine

* **Functional Description**: Coordinates database schema migrations, environment configuration, SSL certificates, Admin Service Role Key authorization, Razorpay integration, and CI/CD production builds.
* **Technical Specs & Capabilities**:
  - **Node.js Production Target**: Node.js v24.20.0 LTS.
  - **Python Production Target**: Python 3.11+.

* **Detailed Input/Output Data Dictionary**:

#### Required Production Environment Variables

#### Backend (`backend/.env`)
| Variable Name | Purpose | Example Value |
| :--- | :--- | :--- |
| `PROJECT_NAME` | Service Name | `"TraceClause AI"` |
| `SUPABASE_URL` | Supabase DB Endpoint | `"https://ubuqluqcugoagtfvyhwg.supabase.co"` |
| `SUPABASE_KEY` | Supabase Anon Key | `"eyJhbGci..."` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Admin Secret Key (**CRITICAL for RLS Bypass**) | `"eyJhbGci..."` |
| `OPENAI_API_KEY` | OpenAI Model Access | `"sk-proj-..."` |
| `GEMINI_API_KEY` | Google Gemini Access | `"AIzaSy..."` |
| `ANTHROPIC_API_KEY` | Claude Model Access | `"sk-ant-..."` |

#### Frontend (`frontend/.env.local`)
| Variable Name | Purpose | Example Value |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | FastAPI Backend Endpoint | `"http://localhost:8000/api/v1"` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Client Endpoint | `"https://ubuqluqcugoagtfvyhwg.supabase.co"` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase Client Key | `"eyJhbGci..."` |
| `NEXT_PUBLIC_RAZORPAY_KEY_ID` | Razorpay Client Public Key | `"rzp_live_..."` |

* **Under-the-Hood Logic & Computations**:
  1. **Database Schema Execution**: Paste the contents of `backend/supabase_schema.sql` into the Supabase SQL Editor to provision `profiles`, `workspaces`, `workspace_members`, `contract_reports` (Audit Vault), and `contract_embeddings` tables with `pgvector` HNSW indexes.
  2. **Frontend Deployment**: Connect `/frontend` to Vercel, set Framework to Next.js, set Node version to 24.20.0 LTS, and configure `NEXT_PUBLIC_` environment variables.
  3. **Backend Deployment**: Deploy `/backend` to Railway/Render with Python 3.11+, setting all secrets including `SUPABASE_SERVICE_ROLE_KEY`, and executing `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

* **Complete Error Handling & Self-Healing Registry**:

| Error Code | HTTP Status | Component | Trigger Condition | Exception Message | Why this HTTP code | Framework Trap / Code Guard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ERR_ENV_MISSING` | 500 | Config Engine | Mandatory env var missing | `Field required` | Internal Server Error | `pydantic-settings` validation |
| `ERR_DB_NOT_FOUND`| 500 | Supabase Engine | Schema SQL not executed | `Relation "profiles" does not exist` | Internal Server Error | SQL Migration Guard |
| `ERR_SERVICE_KEY_MISSING`| 500 | DB Services | `SUPABASE_SERVICE_ROLE_KEY` omitted | `No Supabase DB client available` | Internal Server Error | Admin key fallback guard in `user_isolation.py` |
