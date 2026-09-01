# 02. Points of Failures & Risk Mitigation

This document catalogues potential edge cases, system failure points, context window boundaries, and automated recovery strategies built into **ScanShield AI v2**.

---

## 🛡️ Edge Cases & Automated Mitigations

### 1. Document Parsing Failures (Scanned Image PDFs)

* **Failure Scenario:** Uploaded contract is a scanned image or flattened PDF containing no selectable vector text layer.
* **Impact:** Standard text extractors return an empty string or garbled binary noise.
* **Mitigation Strategy:**
  - Automated fallback detector checks extracted character count per page.
  - If text density $< 50$ characters/page, the system automatically redirects the file to `PyMuPDF` + `Tesseract OCR` or `Mistral OCR API`.
  - Displays user toast: *"Scanned document detected. Running OCR enhancement..."*

---

### 2. Context Window Overflows (Massive 100+ Page Contracts)

* **Failure Scenario:** A 150-page Master Vendor Agreement exceeds the maximum context token window of single-pass LLM prompts.
* **Impact:** Truncation error or expensive $400\text{k}+$ token API calls.
* **Mitigation Strategy:**
  - **Hierarchical Map-Reduce RAG Pipeline:**
    1. Document is split into 1,000-token chunks with 150-token overlap.
    2. Vector DB retrieves top-$k$ candidate risk chunks based on semantic legal query templates (Indemnification, Liability Caps, IP Assignment, Governing Law).
    3. LLM evaluates candidate chunks in parallel batches using Map-Reduce aggregation.

---

### 3. LLM JSON Breakdown & Pydantic Validation Errors

* **Failure Scenario:** LLM output fails to conform to valid JSON formatting due to special character escaping in legal clauses.
* **Impact:** `json.loads()` crash or incomplete API payload.
* **Mitigation Strategy:**
  - Enforce OpenAI / Anthropic `structured_outputs` / `json_schema` response enforcement.
  - Implement a `Pydantic` output parser wrapper with 2 retry attempts:
    - **Attempt 1:** Regex extraction of `{ ... }` code block.
    - **Attempt 2:** Automatic re-prompt to LLM: *"Your previous output failed JSON validation with error X. Re-format strictly as JSON."*

---

### 4. Vector DB Latency & Connection Drops

* **Failure Scenario:** Supabase / pgvector connection times out during peak database loads.
* **Impact:** Document retrieval stalls at the embedding stage.
* **Mitigation Strategy:**
  - Exponential backoff retry loop (3 retries with 1s, 2s, 4s jitter delays).
  - Local in-memory fallback cache (LRU cache) for common standard playbook embeddings.
  - Graceful UI fallback: If vector retrieval fails, system switches to direct clause heuristic regex extraction and alerts the user.

---

## 📊 Summary Matrix

| Failure Mode | Severity | Detection Trigger | Recovery Mechanism |
| :--- | :--- | :--- | :--- |
| **Image-only PDF** | High | Empty text payload ($<50$ chars) | Tesseract / Mistral OCR fallback |
| **Token Limit Exceeded** | Medium | Context length $>128\text{k}$ tokens | Hierarchical Map-Reduce RAG chunking |
| **Malformed LLM JSON** | High | `ValidationError` in Pydantic | Structured output retry prompt (max 2) |
| **Vector DB Timeout** | High | `DBConnectionError` ($>5\text{s}$) | Exponential backoff + LRU heuristic fallback |
