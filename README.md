# 🛡️ ScanShield AI v2 — Enterprise Legal Contract Risk Auditor

An Awwwards-style, enterprise-grade decoupled legal contract audit platform built with **Next.js 15, FastAPI, LangChain, Supabase pgvector, Claude 3.5 Sonnet, and Stripe Monetization**.

![License](https://img.shields.io/badge/license-MIT-indigo.svg)
![Next.js](https://img.shields.io/badge/Next.js-15.0-black.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-emerald.svg)
![Supabase](https://img.shields.io/badge/Supabase-pgvector-emerald.svg)

---

## 🌟 Architecture & Key Features

- **Split-Screen Masterwork Dashboard**: Synchronized 50/50 document viewer & soft-tinted risk cards grid.
- **Plain-English Trap Detection**: Identifies uncapped indemnifications, one-sided liability caps, and IP traps.
- **Redline Counter-Language Generator**: Provides 1-click copyable safer contract wording.
- **Citation-Linked AI Assistant**: Chat drawer where clicking `[Source: Line 13]` citation pills snaps the document viewer directly to the target clause.
- **Stripe Metered Monetization**: Credit tracking engine with Free and Pro subscription tiers.

---

## 📚 Complete System Documentation (`docs/`)

Explore the 8 comprehensive architecture blueprints in the `docs/` folder:

1. [01. Low-Level Wiring & System Data Flow](docs/01-low-level-wiring.md)
2. [02. Points of Failures & Risk Mitigation](docs/02-point-of-failures.md)
3. [03. Frontend Architecture (Next.js UI Blueprint)](docs/03-frontend-architecture.md)
4. [04. Backend Architecture (FastAPI Blueprint)](docs/04-backend-architecture.md)
5. [05. Payment Integration & Monetization Logic](docs/05-payment-integration.md)
6. [06. API Contracts & Token Budget Governance](docs/06-api-contracts-and-limits.md)
7. [07. Evaluation & Quality Assurance (Testing Metrics)](docs/07-test-metrics.md)
8. [08. Deployment Runbook & Production Release](docs/08-deployment-runbook.md)

---

## 🚀 Quickstart Guide

### 1. Backend Setup:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup:
```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` to view the application.
