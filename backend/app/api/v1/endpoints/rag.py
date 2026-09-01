from fastapi import APIRouter, HTTPException
from app.schemas.contract import ChatQueryRequest, ChatQueryResponse
from app.services.vector_store import RAGService

router = APIRouter()
rag_service = RAGService()

@router.post("/chat", response_model=ChatQueryResponse)
async def chat_with_contract(payload: ChatQueryRequest):
    """RAG-powered conversational QA over contract text with source clause citations."""
    if not payload.contract_text.strip() or not payload.question.strip():
        raise HTTPException(status_code=400, detail="Contract text and question must not be empty.")

    try:
        res = rag_service.query_contract(payload.contract_text, payload.question)
        return ChatQueryResponse(answer=res["answer"], citations=res["citations"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")
