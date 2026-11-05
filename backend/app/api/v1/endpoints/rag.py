from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.contract import ChatQueryRequest, ChatQueryResponse
from app.services.vector_store import RAGService
from app.services.user_isolation import UserIsolationService
from app.core.dependencies import require_feature
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()
rag_service = RAGService()

@router.post("/chat", response_model=ChatQueryResponse, dependencies=[Depends(require_feature("rag_interactive_chat"))])
async def chat_with_contract(
    payload: ChatQueryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    RAG-powered conversational QA over contract text with source clause citations.
    Gated behind 'rag_interactive_chat' (Solo & Team tiers).
    Enforces cross-tenant isolation: if a contract_id is specified, verifies user authorization.
    """
    if not payload.contract_text.strip() or not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contract text and question must not be empty."
        )

    # Cross-tenant check if contract_id is provided
    if payload.contract_id:
        report = UserIsolationService.get_user_report_by_id(current_user.id, payload.contract_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract report not found or access denied."
            )

    try:
        res = rag_service.query_contract(payload.contract_text, payload.question)
        return ChatQueryResponse(answer=res["answer"], citations=res["citations"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query failed: {str(e)}"
        )
