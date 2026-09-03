from pydantic import BaseModel, Field
from typing import List, Optional

class ClauseAnalysis(BaseModel):
    clause_number: int
    clause_name: str
    original_text: str
    risk_level: str = Field(..., description="High, Medium, or Low")
    risk_explanation: str
    suggested_counter_language: str = Field(..., description="Safer legal redline counter-language")
    category: Optional[str] = "General"

class AnalysisSummary(BaseModel):
    total_clauses: int
    high_risks: int
    medium_risks: int
    low_risks: int
    overall_risk_score: str

class QuotaInfo(BaseModel):
    quota_used: int
    limit: int
    tier: str
    remaining: int

class ContractAnalysisResponse(BaseModel):
    file_name: str
    extracted_text: str
    summary: AnalysisSummary
    clauses: List[ClauseAnalysis]
    quota_info: Optional[QuotaInfo] = None

class DocumentExtractResponse(BaseModel):
    filename: str
    file_type: str
    char_count: int
    clause_count: int
    text_preview: str
    extracted_text: str

class ChatQueryRequest(BaseModel):
    contract_id: Optional[str] = None
    contract_text: str
    question: str

class ChatQueryResponse(BaseModel):
    answer: str
    citations: List[str]
