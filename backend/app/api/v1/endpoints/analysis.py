import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body, status
from fastapi.responses import StreamingResponse
from app.services.chunking import ChunkingEngine
from app.services.llm_analyzer import LLMAnalyzer
from app.services.user_isolation import UserIsolationService
from app.services.quota_service import QuotaService
from app.services.docx_exporter import DocxExporter
from app.schemas.contract import ContractAnalysisResponse
from app.core.security import get_current_user, AuthenticatedUser
from app.core.dependencies import require_feature

router = APIRouter()
analyzer = LLMAnalyzer()

@router.post("/analyze", response_model=ContractAnalysisResponse)
async def analyze_contract(
    file_name: str = Body(..., embed=True),
    extracted_text: str = Body(..., embed=True),
    retain_audit: bool = Body(True, embed=True),
    workspace_id: Optional[str] = Body(None, embed=True),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Run semantic chunking & LLM clause-risk analysis returning structured redlines.
    Protected endpoint: Enforces atomic database quota reservation and releases quota on failure.
    Supports user-controlled retention and workspace association.
    """
    if not extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extracted contract text cannot be empty."
        )

    user_id = current_user.id
    audit_id = str(uuid.uuid4())

    # Check workspace authorization if workspace_id provided
    if workspace_id:
        from app.core.security import supabase_client
        if supabase_client:
            wm_res = supabase_client.table("workspace_members") \
                .select("id") \
                .eq("workspace_id", workspace_id) \
                .eq("user_id", user_id) \
                .execute()
            if not wm_res.data or len(wm_res.data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You are not an authorized member of the specified workspace."
                )

    # 1. Atomically reserve quota in database
    quota_info = QuotaService.reserve_quota(user_id, audit_id)

    try:
        # 2. Chunk contract and run LLM risk analysis
        clauses = ChunkingEngine.split_into_clauses(extracted_text)
        result = analyzer.analyze_clauses(file_name, extracted_text, clauses)
        result.quota_info = quota_info

        # 3. User-controlled retention: persist only if retain_audit is True
        if retain_audit:
            UserIsolationService.save_user_report(
                user_id=user_id,
                file_name=file_name,
                overall_score=result.summary.overall_risk_score,
                summary_data=result.summary.model_dump(),
                clauses_data=[c.model_dump() for c in result.clauses],
                workspace_id=workspace_id
            )

        # 4. Commit quota reservation upon success
        QuotaService.commit_quota(user_id, audit_id)

        return result
    except HTTPException:
        # Compensating release on HTTP exception
        QuotaService.release_quota(user_id, audit_id)
        raise
    except Exception as e:
        # Compensating release on unexpected failure
        QuotaService.release_quota(user_id, audit_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

@router.get("/my-reports")
async def get_my_reports(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Fetch only authenticated user's historical reports with cross-tenant isolation."""
    user_id = current_user.id
    return UserIsolationService.get_user_reports(user_id)

@router.get("/{report_id}/export-docx", dependencies=[Depends(require_feature("docx_export"))])
async def export_contract_docx(
    report_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Generate and download native .docx redline report for a given contract report.
    Gated behind 'docx_export' feature permission (Solo and Team tiers).
    Enforces cross-tenant isolation: user must be the report owner or an authorized workspace member.
    """
    user_id = current_user.id
    report_data = UserIsolationService.get_user_report_by_id(user_id, report_id)

    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract report not found or access denied."
        )

    try:
        docx_stream = DocxExporter.generate_redline_docx(report_data)
        file_name = report_data.get("file_name", "contract_redline").replace(" ", "_")
        filename_header = f"attachment; filename={file_name}_redline.docx"

        return StreamingResponse(
            docx_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": filename_header}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate .docx redline: {str(e)}"
        )

@router.delete("/{report_id}")
async def delete_contract_report(
    report_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Permanently delete a specific contract report, clause data, and associated vector embeddings.
    Enforces user-controlled retention and verifies ownership before deletion.
    """
    user_id = current_user.id
    deleted = UserIsolationService.delete_user_report(user_id, report_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract report not found or deletion access denied."
        )

    return {
        "status": "success",
        "message": f"Contract report '{report_id}' permanently deleted from Audit Vault."
    }

@router.delete("/delete-account")
async def delete_user_account(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Permanently delete user profile, reports, embeddings, and Supabase Auth account."""
    from app.core.security import supabase_admin, supabase_client
    user_id = current_user.id

    client = supabase_admin or supabase_client
    if client:
        try:
            # Delete user's embeddings
            client.table("contract_embeddings").delete().eq("user_id", user_id).execute()
            # Delete user's reports
            client.table("contract_reports").delete().eq("user_id", user_id).execute()
            # Delete user's quota reservations
            client.table("quota_reservations").delete().eq("user_id", user_id).execute()
            # Delete user profile
            client.table("profiles").delete().eq("id", user_id).execute()
        except Exception:
            pass

    if supabase_admin:
        try:
            supabase_admin.auth.admin.delete_user(user_id)
        except Exception:
            pass

    return {"status": "success", "message": "Account and all associated contract data permanently deleted."}
