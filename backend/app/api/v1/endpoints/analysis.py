from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from app.services.chunking import ChunkingEngine
from app.services.llm_analyzer import LLMAnalyzer
from app.services.user_isolation import UserIsolationService
from app.services.quota_service import QuotaService
from app.services.docx_exporter import DocxExporter
from app.schemas.contract import ContractAnalysisResponse
from app.core.security import get_current_user
from app.core.dependencies import require_feature

router = APIRouter()
analyzer = LLMAnalyzer()

@router.post("/analyze", response_model=ContractAnalysisResponse)
async def analyze_contract(
    file_name: str = Body(..., embed=True),
    extracted_text: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """
    Run semantic chunking & LLM clause-risk analysis returning structured JSON redlines.
    Protected endpoint: Enforces 3 lifetime free audits limit for Free users & saves result.
    """
    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="Extracted contract text cannot be empty.")

    user_id = current_user.id

    # Enforce strict tier quota
    quota_info = QuotaService.check_and_increment_quota(user_id)

    try:
        clauses = ChunkingEngine.split_into_clauses(extracted_text)
        result = analyzer.analyze_clauses(file_name, extracted_text, clauses)
        result.quota_info = quota_info

        # Save under user isolated database storage
        UserIsolationService.save_user_report(
            user_id=user_id,
            file_name=file_name,
            overall_score=result.summary.overall_risk_score,
            summary_data=result.summary.model_dump(),
            clauses_data=[c.model_dump() for c in result.clauses]
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/my-reports")
async def get_my_reports(current_user: dict = Depends(get_current_user)):
    """Fetch only authenticated user's historical reports (User Isolation)."""
    user_id = current_user.id
    return UserIsolationService.get_user_reports(user_id)

@router.get("/{report_id}/export-docx", dependencies=[Depends(require_feature("docx_export"))])
async def export_contract_docx(report_id: str, current_user: dict = Depends(get_current_user)):
    """
    Generate and download native .docx redline report for a given contract report.
    Gated behind 'docx_export' feature permission (Solo and Team tiers only).
    """
    user_id = current_user.id
    reports = UserIsolationService.get_user_reports(user_id)
    report_data = None

    for r in reports:
        if str(r.get("id")) == str(report_id):
            report_data = r
            break

    if not report_data:
        raise HTTPException(status_code=404, detail="Contract report not found or access denied.")

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
        raise HTTPException(status_code=500, detail=f"Failed to generate .docx redline: {str(e)}")

@router.delete("/delete-account")
async def delete_user_account(current_user: dict = Depends(get_current_user)):
    """Permanently delete user from Supabase Auth, profiles, and reports."""
    from app.core.security import supabase_admin
    user_id = getattr(current_user, 'id', None)
    if not user_id or user_id == "demo-user-id":
        return {"status": "success", "message": "Demo user account reset."}

    if supabase_admin:
        try:
            # Delete from Supabase Auth Admin (cascades to profiles & contract_reports)
            supabase_admin.auth.admin.delete_user(user_id)
        except Exception as e:
            print(f"Error deleting auth user: {e}")

    return {"status": "success", "message": "Account permanently deleted."}
