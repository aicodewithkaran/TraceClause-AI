from fastapi import APIRouter
from app.api.v1.endpoints import upload, analysis, rag, payments

api_router = APIRouter()

api_router.include_router(upload.router, prefix="/documents", tags=["documents"])
api_router.include_router(analysis.router, prefix="/contract", tags=["contract-analysis"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag-chat"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])

