# 04. Backend Architecture (FastAPI Blueprint & Modular Code)

This document outlines the directory structure, module responsibilities, Pydantic schemas, and API design for the **FastAPI Backend** of **ScanShield AI v2**.

---

## 📂 Python Backend Directory Blueprint

```text
backend/
├── app/
│   ├── main.py                  # FastAPI app initialization, middleware & CORS
│   ├── api/
│   │   └── v1/
│   │       ├── api.py           # Main Router inclusion
│   │       └── endpoints/
│   │           ├── upload.py    # Document ingestion & parsing endpoint
│   │           ├── analysis.py  # Risk extraction & redline generation
│   │           ├── chat.py      # Citation-linked contract Q&A streaming
│   │           └── billing.py   # Stripe checkout & webhook listener
│   ├── core/
│   │   ├── config.py            # Pydantic BaseSettings & env configuration
│   │   └── security.py          # API key validation & rate limiting
│   ├── schemas/
│   │   ├── contract.py          # Pydantic schemas for upload & parsing
│   │   ├── risk.py              # Pydantic schemas for risk cards & redlines
│   │   └── chat.py              # Pydantic schemas for citation chat
│   └── services/
│       ├── parser.py            # LlamaParse / PyMuPDF OCR extraction
│       ├── rag_service.py       # Supabase pgvector embedding & retrieval
│       ├── llm_service.py       # Claude 3.5 Sonnet / GPT-4o risk analysis
│       └── stripe_service.py    # Billing & quota tracking
├── requirements.txt             # Dependency manifest
└── uvicorn_start.sh             # Local server startup script
```

---

## 📋 Core Pydantic Schemas

### 1. Risk Analysis Output Schema (`schemas/risk.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Literal

class RiskCard(BaseModel):
    id: str = Field(..., description="Unique risk identifier")
    title: str = Field(..., description="Section header & risk title")
    level: Literal["high", "medium", "low"] = Field(..., description="Risk severity level")
    line: int = Field(..., description="Target line number in parsed document")
    trap: str = Field(..., description="Plain-English explanation of danger for user")
    redline: str = Field(..., description="Recommended counter-language wording")

class ContractAnalysisResponse(BaseModel):
    contract_id: str
    filename: str
    compliance_score: int = Field(..., ge=0, le=100)
    summary: str
    total_risks: int
    risks: List[RiskCard]
```

### 2. Citation Chat Schema (`schemas/chat.py`)

```python
from pydantic import BaseModel
from typing import Optional

class ChatQueryRequest(BaseModel):
    contract_id: str
    question: str
    playbook: Optional[str] = "standard"

class ChatCitationResponse(BaseModel):
    sender: str = "ai"
    answer: str
    referenced_line: Optional[int] = None
    citation_tag: str  # e.g., "[Source: Line 13]"
```

---

## ⚙️ Module Responsibilities

| Module | Primary Responsibility | Key Libraries |
| :--- | :--- | :--- |
| `parser.py` | Ingests PDF/Docx bytes, runs OCR if scanned, returns structured text lines | `PyMuPDF`, `python-docx`, `LlamaParse` |
| `rag_service.py` | Generates vector embeddings, queries Supabase HNSW index for top-$k$ legal clauses | `langchain`, `supabase-py`, `pgvector` |
| `llm_service.py` | Sends context chunks to Claude 3.5 Sonnet / GPT-4o, validates Pydantic JSON outputs | `openai`, `anthropic`, `pydantic` |
| `billing.py` | Listens to Stripe webhooks, decrements user contract review credits | `stripe`, `fastapi` |
