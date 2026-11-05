import uuid
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.schemas.job import (
    ContractJobCreateRequest, 
    ContractJobCreateResponse, 
    ContractJobStatusResponse
)
from app.core.security import get_current_user, AuthenticatedUser
from app.services.job_worker import JobWorker
from app.core.config import settings
from supabase import create_client

router = APIRouter()
worker = JobWorker()

def _get_supabase_admin():
    if settings.SUPABASE_URL and settings.supabase_admin_key:
        return create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
    if settings.SUPABASE_URL and settings.supabase_anon_key:
        return create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
    return None

@router.post("/submit", response_model=ContractJobCreateResponse)
async def submit_analysis_job(
    req: ContractJobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Submits a contract analysis job to the durable PostgreSQL queue.
    Atomically verifies effective subscription tier, pools team quota against workspace owner,
    enforces maximum 2 concurrent active jobs per user, reserves quota, and stages extracted text.
    Returns in < 200ms with a unique job ID.
    """
    if not req.extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contract extracted text cannot be empty."
        )

    supabase = _get_supabase_admin()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Request failed closed."
        )

    user_id = current_user.id
    audit_reservation_id = str(uuid.uuid4())

    try:
        rpc_res = supabase.rpc("create_contract_analysis_job", {
            "p_user_id": user_id,
            "p_file_name": req.file_name,
            "p_extracted_text": req.extracted_text,
            "p_audit_reservation_id": audit_reservation_id,
            "p_workspace_id": req.workspace_id,
            "p_retain_audit": req.retain_audit
        }).execute()

        data = rpc_res.data
        if not data or "job_id" not in data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue contract analysis job."
            )

        # Trigger worker immediately in background to claim and process the job
        background_tasks.add_task(worker.claim_and_run_one)

        return ContractJobCreateResponse(
            job_id=data["job_id"],
            audit_reservation_id=data.get("audit_reservation_id", audit_reservation_id),
            tier=data.get("tier", "free"),
            status="queued",
            usage_after_reservation=data.get("usage_after_reservation", 1),
            tier_limit=data.get("tier_limit", 3)
        )
    except HTTPException:
        raise
    except Exception as e:
        err_str = str(e)
        if "Concurrency limit exceeded" in err_str:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Concurrency limit exceeded: maximum 2 active analysis jobs permitted at a time. Please wait for previous jobs to complete."
            )
        if "QUOTA_EXCEEDED" in err_str:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Contract audit limit reached for your subscription tier. Please upgrade to continue."
            )
        if "Team workspace owner subscription is expired" in err_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Team workspace owner subscription has expired. Audits are suspended until renewed."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job creation failed: {err_str}"
        )

@router.get("/{job_id}", response_model=ContractJobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Retrieves the real-time status and progress of a contract analysis job.
    Strict tenant isolation: non-owners cannot inspect other users' jobs.
    """
    supabase = _get_supabase_admin()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable."
        )

    res = supabase.table("contract_analysis_jobs") \
        .select("id, user_id, file_name, status, progress_percent, stage_message, report_id, error_message") \
        .eq("id", job_id) \
        .execute()

    if not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found."
        )

    job = res.data[0]
    # Enforce strict tenant isolation
    if job["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found."
        )

    result_data = None
    if job.get("status") == "completed" and job.get("report_id"):
        rep_res = supabase.table("contract_reports") \
            .select("id, overall_risk_score, summary_json, clauses_json") \
            .eq("id", job["report_id"]) \
            .execute()
        if rep_res.data and len(rep_res.data) > 0:
            result_data = rep_res.data[0]

    return ContractJobStatusResponse(
        id=job["id"],
        file_name=job["file_name"],
        status=job["status"],
        progress_percent=job.get("progress_percent", 0),
        stage_message=job.get("stage_message", "Processing..."),
        report_id=job.get("report_id"),
        error_message=job.get("error_message"),
        result=result_data
    )

