# 09. Interview Deep-Dive: End-to-End RAG Architecture & Legal Audit Engine

> 💡 **Purpose:** This document serves as your complete technical interview master guide for explaining the backend architecture, RAG pipeline, LLM governance, and report generation engine of **TraceClause AI** (ScanShield AI v2).

---

## 🏛️ Executive High-Level Architecture Overview

When an interviewer asks: *"Can you walk me through the backend architecture of your legal contract AI platform?"*, use this structured framework:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             END-TO-END RAG PIPELINE                              │
└──────────────────────────────────────────────────────────────────────────────────┘

 [Client Dropzone]
        │ (1. Multipart Upload)
        ▼
 [FastAPI Controller] ──► [File Validator] ──► (Validates extension & size <50MB)
        │
        │ (2. Text Extraction & OCR)
        ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ PARSER SERVICE (PyMuPDF / LlamaParse / Tesseract OCR)                  │
 │ • Extracts raw text stream while preserving section headings & lines   │
 │ • Fallback Trigger: If char count < 50/page ➔ Run OCR Image Parser     │
 └────────────────────────────────────────────────────────────────────────┘
        │
        │ (3. Hierarchical Semantic Chunking)
        ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ SEMANTIC CHUNKER SERVICE                                               │
 │ • Chunk Size: 1,000 tokens | Overlap: 150 tokens                       │
 │ • Boundary Detection: Splits on clause headers (e.g. "Section 8.2")    │
 └────────────────────────────────────────────────────────────────────────┘
        │
        │ (4. Vector Embedding Ingestion)
        ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ EMBEDDING ENGINE (OpenAI text-embedding-3-small)                       │
 │ • Generates 1536-dimensional dense vector embeddings                  │
 └────────────────────────────────────────────────────────────────────────┘
        │
        │ (5. HNSW Vector Indexing & Storage)
        ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ SUPABASE PGVECTOR DATABASE                                             │
 │ • Stores chunk metadata (line_start, line_end, section_title, vector)  │
 │ • Index Type: HNSW (Hierarchical Navigable Small World) - Cosine Dist  │
 └────────────────────────────────────────────────────────────────────────┘
        │
        │ (6. Context-Retrieved Playbook Querying)
        ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ RAG RETRIEVER & HYBRID SEARCH                                          │
 │ • Queries vector DB for playbook clauses (Indemnification, Caps, IP)   │
 │ • Fetches top-k candidate chunks (k=5) with cosine similarity > 0.78   │
 └────────────────────────────────────────────────────────────────────────┘
        │
        │ (7. Multi-Stage Structured LLM Reasoning)
        ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ LLM AUDITOR SERVICE (Claude 3.5 Sonnet / GPT-4o)                       │
 │ • Evaluates candidate chunks against custom Playbook baseline          │
 │ • Pydantic Schema Enforcement: Generates "The Trap" & "Redline Wording" │
 └────────────────────────────────────────────────────────────────────────┘
        │
        │ (8. Response & Audit Report Generation)
        ▼
 [FastAPI JSON / SSE Response] ──► [Next.js Split-Screen Dashboard & PDF Exporter]
```

---

## 🔍 Deep-Dive: The 8 Pipeline Stages Explained for Interviews

### Stage 1: Document Upload & Input Validation (`routers/upload.py`)
- **How it works:** User uploads a `.pdf` or `.docx` contract via Next.js `FileDropzone`. FastAPI receives a `UploadFile` multipart stream.
- **Key Technical Details:**
  - File size validation capped at $50\text{MB}$.
  - MIME-type verification checking magic bytes (e.g., `%PDF-` header) to prevent malicious executable uploads.

---

### Stage 2: Dual-Engine Text Extraction & OCR Fallback (`services/parser.py`)
- **How it works:** Converts binary document streams into line-numbered raw text objects (`{ line_number: 1, text: "Section 8.2 Indemnification", is_header: True }`).
- **Interview Highlight (Handling Scanned PDFs):**
  - Standard text extractors (`PyPDF2` / `PyMuPDF`) fail on scanned image-based PDFs.
  - **Fallback Logic:** Our parser computes character density per page ($\text{chars/page}$). If density $< 50$, the system automatically routes the page image to `Tesseract OCR` or `Mistral OCR API`.

---

### Stage 3: Hierarchical Legal Semantic Chunking (`services/chunker.py`)
- **Why Naive Fixed-Size Chunking Fails in Legal:** Arbitrary 500-token chunks often split a single indemnification clause right down the middle, separating the obligation from its monetary cap!
- **Our Solution (Legal Boundary-Aware Chunking):**
  - Respects section boundaries (`Section`, `Clause`, `Article`, `Schedule`).
  - Chunk size: $1,000$ tokens with a $150$-token sliding overlap window to preserve inter-clause context.

---

### Stage 4: Embedding Generation (`services/embedding.py`)
- **Model Used:** OpenAI `text-embedding-3-small` ($1536$ dimensions).
- **Why `text-embedding-3-small`:** Outstanding cost-to-performance ratio ($0.02 / 1\text{M}$ tokens) and superior legal semantic retrieval capabilities compared to older `ada-002` models.

---

### Stage 5: Vector DB Indexing & Storage (`services/rag_service.py`)
- **Database:** **Supabase PostgreSQL** with `pgvector` extension.
- **Index Algorithm:** **HNSW (Hierarchical Navigable Small World)** indexing using Cosine Distance (`vector_cosine_ops`).
- **Why HNSW over IVFFlat:** HNSW provides faster query response times ($<50\text{ms}$) and does not require pre-training clusters on small dataset initializations.

---

### Stage 6: Playbook Baseline Retrieval & Hybrid Search
- **How Retrieval Works:**
  1. The user selects an Audit Playbook (*Standard Enterprise MSA*, *Vendor Defense*, *Founder Friendly*).
  2. The system executes vector similarity search comparing baseline playbook risk queries against the stored contract chunks.
  3. Top-$k$ chunks ($k=5$) with cosine similarity $>0.78$ are retrieved along with metadata (`line_number_start`, `line_number_end`).

---

### Stage 7: LLM Legal Audit & Pydantic Schema Enforcement (`services/llm_service.py`)
- **Models Used:** `Claude 3.5 Sonnet` (for complex legal reasoning & redlining) or `GPT-4o` (for rapid risk triage).
- **Structured Outputs (Pydantic Schema):**
  The prompt instructs the LLM to output JSON conforming strictly to:
  ```python
  class RiskCard(BaseModel):
      title: str      # e.g., "Section 8.2: Uncapped Indemnification"
      level: str      # "high", "medium", "low"
      line: int       # Target line number
      trap: str       # Plain-English explanation of danger
      redline: str    # Counter-language wording
  ```
- **Self-Correction & Retry Loop:** If the LLM returns invalid JSON or fails schema validation, the `ValidationError` triggers an automatic retry prompt providing the error trace to the LLM.

---

### Stage 8: Audit Report Generation & Citation UI Sync
- **Front-End Synchronization:** The API returns JSON payload to Next.js.
- **Citation Pills:** AI Chat drawer generates `[Source: Line 13]` citation badges. Clicking a badge triggers `element.scrollIntoView({ behavior: 'smooth' })` and pulses the line on the left-hand document viewer!

---

## 🎯 Common Interview Questions & Winning Answers

### Q1: "How do you handle LLM hallucinations in legal contract analysis?"
> **Answer:** We mitigate hallucinations using 3 strict layers:
> 1. **RAG Grounding:** The LLM is restricted to analyzing only the retrieved contract chunks.
> 2. **Line Citation Verification:** Every flagged risk must output the exact source line number. If the LLM cannot cite a specific line number, the claim is rejected.
> 3. **Pydantic Validation:** Strict schema enforcement ensures zero conversational fluff.

---

### Q2: "What happens if a contract is 200 pages long and exceeds the LLM context window?"
> **Answer:** We employ a **Map-Reduce RAG Strategy**. Instead of dumping the full 200 pages into a prompt, we chunk the document, retrieve only the candidate clauses matching high-risk legal patterns (Indemnification, Caps, IP, Termination), and audit those candidates in parallel batches.

---

### Q3: "Why did you choose FastAPI over Flask or Django for the AI backend?"
> **Answer:** FastAPI is built natively on `ASGI` with `async/await` support, making it ideal for handling asynchronous I/O-bound LLM API calls and SSE streaming without blocking main server threads. Additionally, its native integration with `Pydantic` gives us automatic OpenAPI docs and runtime type safety.
