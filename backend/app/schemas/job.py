from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ContractJobCreateRequest(BaseModel):
    file_name: str
    extracted_text: str
    workspace_id: Optional[str] = None
    retain_audit: bool = True

class ContractJobCreateResponse(BaseModel):
    job_id: str
    audit_reservation_id: str
    tier: str
    status: str
    usage_after_reservation: int
    tier_limit: int

class ContractJobStatusResponse(BaseModel):
    id: str
    file_name: str
    status: str
    progress_percent: int
    stage_message: str
    report_id: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

