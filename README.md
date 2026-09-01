# 🛡️ TraceClause AI (ScanShield AI v2) — Enterprise Legal Contract Auditor

An Awwwards-style, enterprise-grade decoupled legal contract audit platform built with **Next.js 15, FastAPI, LangChain, Supabase pgvector, Claude 3.5 Sonnet / GPT-4o, and Stripe Monetization**.

![License](https://img.shields.io/badge/license-MIT-indigo.svg)
![Next.js](https://img.shields.io/badge/Next.js-15.0-black.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-emerald.svg)
![Supabase](https://img.shields.io/badge/Supabase-pgvector-emerald.svg)
![Python](https://img.shields.io/badge/Python-3.12-blue.svg)

---

## 🌟 Overview & Key Capabilities

**TraceClause AI** transforms unstructured, lengthy legal contracts into high-precision, actionable risk audits. Built for law firms, legal tech teams, and document-heavy operations:

- **Split-Screen Masterwork Dashboard**: Synchronized 50/50 line-numbered document viewer & soft-tinted risk cards grid.
- **The Trap & Redline Generator**: Plain-English explanations of dangerous clauses + 1-click copyable counter-language wording.
- **Citation-Linked AI Assistant**: Interactive chat drawer where clicking `[Source: Line 13]` citation pills automatically snaps the document viewer to the exact target clause.
- **OCR-Enabled Processing**: Automatic fallback for scanned image PDFs using `PyMuPDF` + `Tesseract` / `Mistral OCR`.
- **Baseline Audit Playbooks**: Customizable strictness matching (*Standard Enterprise MSA*, *Vendor Defense*, *Founder Friendly*).
- **Stripe Monetization Engine**: Metered credit tracking system with Free (2 audits) and Pro ($49/mo) tiers.

---

## 🏗️ Tech Stack

| Layer | Technologies Used |
| :--- | :--- |
| **Frontend** | Next.js 15, React 19, Tailwind CSS v4, Lucide Icons, Zustand / React Context |
| **Backend API** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, Slowapi Rate Limiter |
| **Parsing & OCR** | PyMuPDF, python-docx, LlamaParse, Tesseract OCR |
| **Vector DB & RAG** | Supabase PostgreSQL (`pgvector`), OpenAI `text-embedding-3-small` (HNSW Index) |
| **LLM Reasoning** | Anthropic Claude 3.5 Sonnet, OpenAI GPT-4o |
| **Monetization** | Stripe SDK (Checkout Sessions & Webhook Event Listeners) |

---

## 📚 Complete System Documentation (`docs/`)

Explore our comprehensive 9-part production architecture and interview preparation specifications:

1. 📄 [01. Low-Level Wiring & System Data Flow](docs/01-low-level-wiring.md)
2. 📄 [02. Points of Failures & Risk Mitigation](docs/02-point-of-failures.md)
3. 📄 [03. Frontend Architecture (Next.js UI Blueprint)](docs/03-frontend-architecture.md)
4. 📄 [04. Backend Architecture (FastAPI Blueprint)](docs/04-backend-architecture.md)
5. 📄 [05. Payment Integration & Monetization Logic](docs/05-payment-integration.md)
6. 📄 [06. API Contracts & Token Budget Governance](docs/06-api-contracts-and-limits.md)
7. 📄 [07. Evaluation & Quality Assurance (Testing Metrics)](docs/07-test-metrics.md)
8. 📄 [08. Deployment Runbook & Production Release](docs/08-deployment-runbook.md)
9. 🎓 [09. Interview Deep-Dive: RAG Architecture & Legal Audit Engine](docs/09-interview-rag-architecture-deep-dive.md)

---

## ⚡ Local Setup & Installation Guide

### Prerequisites
- Python 3.12+
- Node.js 18+
- Supabase Account (or PostgreSQL with `pgvector`)

---

### 1. Backend Setup (FastAPI)

```bash
# Navigate to backend folder
cd backend

# Activate virtual environment
source venv/bin/activate

# Install dependencies (if needed)
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
ANTHROPIC_API_KEY="sk-ant-..."
LLAMAPARSE_API_KEY="llx-..."

SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="eyJhbGci..."
DATABASE_URL="postgresql://postgres:password@db.your-project.supabase.co:5432/postgres"

STRIPE_SECRET_KEY="sk_test_..."
STRIPE_WEBHOOK_SECRET="whsec_..."
```

### Frontend `.env.local` (`/frontend/.env.local`)

```env
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000/api/v1"
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY="pk_test_..."
```

---

## 🌐 REST API Endpoints Summary

| Method | Endpoint Route | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/upload` | Ingests PDF/Word contract & runs parsing |
| `POST` | `/api/v1/analysis` | Audits contract clauses against Playbook baseline |
| `POST` | `/api/v1/chat` | Citation-linked contract Q&A streaming |
| `POST` | `/api/v1/billing/create-checkout` | Generates Stripe Checkout Session |
| `POST` | `/api/v1/billing/webhook` | Handles Stripe subscription webhook events |

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
