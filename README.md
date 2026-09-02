# 🛡️ TraceClause AI (ScanShield AI v2) — Enterprise Legal Contract Auditor

An Awwwards-style, enterprise-grade decoupled legal contract audit platform built with **Next.js 16, FastAPI, LangChain, Supabase pgvector, Multi-LLM (Claude 3.5 Sonnet / GPT-4o / Gemini 1.5 Pro), Stripe & Razorpay Monetization, and Native .docx Redline Exports**.

![License](https://img.shields.io/badge/license-MIT-indigo.svg)
![Next.js](https://img.shields.io/badge/Next.js-16.0-black.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-emerald.svg)
![Supabase](https://img.shields.io/badge/Supabase-pgvector-emerald.svg)
![Python](https://img.shields.io/badge/Python-3.12-blue.svg)

---

## 🌟 Overview & Key Capabilities

**TraceClause AI** transforms unstructured, lengthy legal contracts into high-precision, actionable risk audits. Built for law firms, legal tech teams, and document-heavy operations:

- **2-Tier B2B Monetization & Hard-Capped Free Trial**: 3 Lifetime Total Free Audits (hard stop limit), Solo Plan ($79/mo - 20 reviews), and Team Plan ($299/mo - 100 pooled reviews + 4 workspace seats).
- **Feature-Gated Authorization Guard**: FastAPI middleware (`require_feature`) enforcing tier-specific permissions across interactive RAG, `.docx` exports, and shared workspaces.
- **Native Word (.docx) Redline Export Engine**: Generates Microsoft Word `.docx` documents featuring strikethrough red original text, green underlined counter-language recommendations, and shaded callout boxes detailing risk rationale.
- **Native 1536-Dim Vector Normalization**: Requests 1536 native dimensions from `gemini-embedding-001` via Matryoshka Representation Learning (`config={"output_dimensionality": 1536}`), completely eliminating vector zero-padding.
- **Multi-Seat Workspaces**: Team tier workspace collaboration with role-based member management and workspace-aware Row Level Security (RLS) policies.
- **Split-Screen Masterwork Dashboard**: Synchronized 50/50 line-numbered document viewer & soft-tinted risk cards grid.
- **Dual Payment Gateways**: International Stripe Checkout (USD) & India Razorpay Checkout (INR / UPI / Cards).

---

## 🏗️ Tech Stack

| Layer | Technologies Used |
| :--- | :--- |
| **Frontend** | Next.js 16, React 19, Tailwind CSS v3/v4, Lucide Icons, React Context |
| **Backend API** | Python 3.12, FastAPI, Uvicorn, Pydantic v2 |
| **Parsing & Export** | PyMuPDF, python-docx (Native Word Redlines) |
| **Vector DB & RAG** | Supabase PostgreSQL (`pgvector`), OpenAI `text-embedding-3-small` & Gemini `gemini-embedding-001` (1536-dim MRL, HNSW Index) |
| **LLM Reasoning** | Anthropic Claude 3.5 Sonnet, OpenAI GPT-4o, Google Gemini 1.5 Pro |
| **Monetization** | Stripe SDK (USD International) & Razorpay SDK (INR / UPI / Local India) |

---

## 📚 Complete System Documentation (`docs/`)

Explore our comprehensive 11-part production architecture and interview preparation specifications:

1. 📄 [01. Low-Level Wiring & System Data Flow](docs/01-low-level-wiring.md)
2. 📄 [02. Points of Failures & Risk Mitigation](docs/02-point-of-failures.md)
3. 📄 [03. Frontend Architecture (Next.js UI Blueprint)](docs/03-frontend-architecture.md)
4. 📄 [04. Backend Architecture (FastAPI Blueprint)](docs/04-backend-architecture.md)
5. 📄 [05. Payment Integration & Monetization Logic](docs/05-payment-integration.md)
6. 📄 [06. API Contracts & Token Budget Governance](docs/06-api-contracts-and-limits.md)
7. 📄 [07. Evaluation & Quality Assurance (Testing Metrics)](docs/07-test-metrics.md)
8. 📄 [08. Deployment Runbook & Production Release](docs/08-deployment-runbook.md)
9. 🎓 [09. Interview Deep-Dive: RAG Architecture & Legal Audit Engine](docs/09-interview-rag-architecture-deep-dive.md)
10. 📄 [10. System Architecture, Env & Database Roadmap](docs/10-system-architecture-env-db-roadmap.md)
11. 📄 [11. Database Schema & Vector Storage Deep Dive](docs/11-database-schema-vector-storage-deep-dive.md)

---

## ⚡ Local Setup & Installation Guide

### Prerequisites
- Python 3.12+
- Node.js 22+ / 24 LTS (Required by `@supabase/supabase-js` v2.109+)
- Supabase Account (or PostgreSQL with `pgvector`)

---

### 1. Backend Setup (FastAPI)

```bash
# Navigate to backend folder
cd backend

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```
- **Backend API Base**: `http://localhost:8000/`
- **Interactive OpenAPI Docs**: `http://localhost:8000/docs`

---

### 2. Frontend Setup (Next.js)

```bash
# Open new terminal & navigate to frontend folder
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```
- **Frontend App**: `http://localhost:3000/`

---

## 🔑 Environment Variables Reference

### Backend `.env` (`/backend/.env`)

```env
PROJECT_NAME="TraceClause AI Backend"
VERSION="2.0.0"
API_V1_STR="/api/v1"
ALLOWED_ORIGINS="http://localhost:3000,https://traceclause.vercel.app"

OPENAI_API_KEY="sk-proj-..."
GEMINI_API_KEY="AIzaSy..."
ANTHROPIC_API_KEY="sk-ant-..."

SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="eyJhbGci..."
SUPABASE_SERVICE_ROLE_KEY="eyJhbGci..."

STRIPE_SECRET_KEY="sk_test_..."
RAZORPAY_KEY_ID="rzp_test_..."
RAZORPAY_KEY_SECRET="..."
```

---

## 🌐 REST API Endpoints Summary

| Method | Endpoint Route | Feature Guard | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/documents/upload` | Open | Ingests PDF/Word contract & extracts RAM text |
| `POST` | `/api/v1/contract/analyze` | Quota Check | Audits contract clauses & generates AI redlines |
| `GET` | `/api/v1/contract/my-reports` | Authenticated | Fetches user's historical audit reports |
| `GET` | `/api/v1/contract/{report_id}/export-docx` | `docx_export` | Generates and streams native Word `.docx` redline report |
| `POST` | `/api/v1/rag/chat` | `rag_interactive_chat` | Citation-linked contract RAG Q&A |
| `GET/POST`| `/api/v1/workspaces/` | `workspace_management` | Manages team workspaces & workspace seats |
| `POST` | `/api/v1/payments/stripe/create-checkout-session` | Open | Stripe Checkout for USD ($79 Solo / $299 Team) |
| `POST` | `/api/v1/payments/razorpay/create-order` | Open | Razorpay Order for INR (₹7,499 Solo / ₹27,999 Team) |

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
