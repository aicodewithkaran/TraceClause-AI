# 01. Low-Level Wiring & System Data Flow

This document details the low-level technical architecture, end-to-end data pipeline flow, environment configuration, and local dev startup sequence for **ScanShield AI v2**.

---

## 🏗️ End-to-End Data Pipeline Architecture

```
[User PDF / Word Upload] 
         │
         ▼
[Next.js 15 Client Dropzone] ──(Multipart POST)──► [FastAPI Router /api/v1/upload]
                                                              │
                                                              ▼
                                               [Unstructured / LlamaParse Engine]
                                               (OCR Fallback via PyMuPDF/Tesseract)
                                                              │
                                                              ▼
                                               [Hierarchical Semantic Chunking]
                                               (Token windowing & overlap)
                                                              │
                                                              ▼
                                               [OpenAI / Cohere Embedding API]
                                               (text-embedding-3-small)
                                                              │
                                                              ▼
                                               [Supabase pgvector DB Storage]
                                               (HNSW Vector Indexing)
                                                              │
                                                              ▼
                                               [Claude 3.5 Sonnet / GPT-4o LLM]
                                               (Pydantic Structured Risk Extraction)
                                                              │
                                                              ▼
                                               [FastAPI SSE Stream / Response]
                                                              │
                                                              ▼
                                               [Next.js Split-Screen UI Dashboard]
```

---

## 🔄 End-to-End Request Cycle Breakdown

1. **Client Document Upload**:
   - User drops a contract (`.pdf`, `.docx`) into the Next.js `FileDropzone` component.
   - Client sends an asynchronous `POST /api/v1/upload` request with `FormData`.

2. **Parser & OCR Ingestion**:
   - FastAPI receives the binary payload and forwards it to `LlamaParse` or `Unstructured API`.
   - If the document contains image-only scans, the pipeline triggers an automatic OCR fallback using `PyMuPDF` + `Tesseract` / `Mistral OCR`.

3. **Semantic Chunking & Vector Ingestion**:
   - Extracted text is segmented into semantic blocks (preserving section headings like `Section 8.2 Indemnification`).
   - Embeddings are generated via `text-embedding-3-small` and indexed into `Supabase pgvector` using an HNSW vector index.

4. **Multi-Stage LLM Risk Audit**:
   - Top-$k$ relevant chunks are retrieved and passed to `Claude 3.5 Sonnet` / `GPT-4o`.
   - The LLM identifies non-standard clauses, plain-English "Traps", and produces counter-language "Redlines" conforming strictly to a `Pydantic` schema.

5. **Client UI State Update**:
   - FastAPI returns the structured payload. The Next.js client renders the split-screen dashboard, pulsing active line highlights when risk cards are selected.

---

## 🔑 Environment Variables Reference (`.env`)

### Backend (`/backend/.env`)

```env
# Server Configuration
PROJECT_NAME="ScanShield AI Backend"
VERSION="2.0.0"
API_V1_STR="/api/v1"
ALLOWED_ORIGINS="http://localhost:3000,https://scanshield.vercel.app"

# AI & LLM Providers
OPENAI_API_KEY="sk-proj-..."
ANTHROPIC_API_KEY="sk-ant-..."
LLAMAPARSE_API_KEY="llx-..."

# Supabase Vector Database
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOi..."
DATABASE_URL="postgresql://postgres:password@db.your-project.supabase.co:5432/postgres"

# Stripe Monetization
STRIPE_SECRET_KEY="sk_test_..."
STRIPE_WEBHOOK_SECRET="whsec_..."
```

### Frontend (`/frontend/.env.local`)

```env
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000/api/v1"
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY="pk_test_..."
```

---

## ⚡ Local Startup Shell Commands

### 1. Start FastAPI Backend:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 2. Start Next.js Frontend:
```bash
cd frontend
npm run dev -- -p 3000
```
