# 07. Evaluation & Quality Assurance (Testing Metrics)

This document details automated testing strategy, **RAG Evaluation Frameworks** (Ragas / TruLens), and latency benchmarks for **ScanShield AI v2**.

---

## 🧪 Testing Suite Architecture

```
 ┌─────────────────────────────────────────────────────────────┐
 │                      TESTING FRAMEWORKS                     │
 ├──────────────────────────────┬──────────────────────────────┤
 │       BACKEND TESTING        │       FRONTEND TESTING       │
 │ • Pytest (Unit & Integration)│ • Playwright (End-to-End E2E)│
 │ • Ragas / TruLens (RAG Eval) │ • Jest / React Testing Lib   │
 └──────────────────────────────┴──────────────────────────────┘
```

---

## 🎯 RAG Evaluation Metrics (Ragas Framework)

Legal risk extraction requires near-zero hallucination rates and exact clause retrieval accuracy:

### Evaluated RAG Metrics:

1. **Faithfulness (Anti-Hallucination):**
   - Measures if the generated "Trap" explanation is strictly grounded in the retrieved legal clause context.
   - **Target Benchmark:** $> 0.95$

2. **Answer Relevancy:**
   - Measures if the generated redline counter-language directly addresses the risk identified.
   - **Target Benchmark:** $> 0.92$

3. **Context Recall & Precision:**
   - Measures if the vector retriever fetched the actual line containing indemnification or liability caps.
   - **Target Benchmark:** $> 0.90$

---

## ⚙️ Running Automated Tests

### 1. Execute Backend Pytest Suite:

```bash
cd backend
source venv/bin/activate
pytest tests/ -v --cov=app
```

### 2. Execute RAG Evaluation Benchmark Script:

```bash
cd backend
python scripts/eval_ragas.py
```

### 3. Execute Frontend Playwright E2E Tests:

```bash
cd frontend
npx playwright test
```

---

## ⏱️ Target Performance Benchmarks

| Milestone Operation | Target Response Time | SLA Threshold |
| :--- | :--- | :--- |
| **Document Text Extraction (15 pages)** | $< 1.2\text{ seconds}$ | $< 3.0\text{ seconds}$ |
| **Vector Embedding & DB Storage** | $< 800\text{ ms}$ | $< 1.5\text{ seconds}$ |
| **Full LLM Risk Analysis (5 Cards)** | $< 3.5\text{ seconds}$ | $< 6.0\text{ seconds}$ |
| **Citation Chat Query Response** | $< 1.8\text{ seconds}$ | $< 4.0\text{ seconds}$ |
