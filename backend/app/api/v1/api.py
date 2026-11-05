from fastapi import APIRouter
from app.api.v1.endpoints import upload, analysis, rag, payments, workspace, jobs, health

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(upload.router, prefix="/documents", tags=["documents"])
api_router.include_router(analysis.router, prefix="/contract", tags=["contract-analysis"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["contract-jobs"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag-chat"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(workspace.router, prefix="/workspaces", tags=["workspaces"])

