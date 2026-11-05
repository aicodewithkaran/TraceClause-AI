import os
import uuid
import asyncio
import logging
from typing import Optional, Dict, Any
from supabase import create_client, Client
from app.core.config import settings
from app.services.chunking import ChunkingEngine
from app.services.llm_analyzer import LLMAnalyzer
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)

class JobWorker:
    """
    Durable Background Worker for Contract Analysis Jobs:
    - Claims jobs using PostgreSQL FOR UPDATE SKIP LOCKED with fencing tokens.
    - Updates progress and heartbeats periodically.
    - Computes clause chunking, LLM risk scoring, and 1536-dim vector embeddings.
    - Transactionally commits or rolls back quotas on completion/failure.
    - Staged contract text is purged immediately upon completion or failure.
    """

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker_{os.getpid()}_{uuid.uuid4().hex[:6]}"
        if settings.SUPABASE_URL and settings.supabase_admin_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
        elif settings.SUPABASE_URL and settings.supabase_anon_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
        else:
            self.supabase = None

        self.analyzer = LLMAnalyzer()
        self.vector_store = VectorStoreService()

    async def execute_job(self, job_data: Dict[str, Any]) -> bool:
        """
        Executes a claimed contract analysis job.
        Every state transition verifies the fencing token.
        """
        if not self.supabase:
            return False

        job_id = job_data["job_id"]
        token = job_data["fencing_token"]
        file_name = job_data["file_name"]
        user_id = job_data["user_id"]
        workspace_id = job_data.get("workspace_id")
        retain_audit = job_data.get("retain_audit", True)
        extracted_text = job_data.get("extracted_text") or ""

        if not extracted_text.strip():
            self._fail_job(job_id, token, "Extracted text was empty")
            return False

        try:
            # Step 1: Chunking (Progress: 20%)
            self._update_progress(job_id, token, 20, "Extracting and segmenting clauses...")
            clauses = ChunkingEngine.split_into_clauses(extracted_text)

            # Step 2: LLM Risk Analysis (Progress: 50%)
            self._update_progress(job_id, token, 50, "Evaluating legal risks and generating redlines...")
            # Run analysis in threadpool to avoid blocking async event loop
            result = await asyncio.to_thread(
                self.analyzer.analyze_clauses, file_name, extracted_text, clauses
            )

            report_id = None
            if retain_audit:
                # Step 3: Embeddings Generation (Progress: 80%)
                self._update_progress(job_id, token, 80, "Indexing semantic vector embeddings...")
                clause_texts = [c.original_text for c in result.clauses]
                embeddings = await asyncio.to_thread(
                    self.vector_store.generate_embeddings_batch, clause_texts
                )

                # Step 4: Persist Report (Progress: 95%)
                self._update_progress(job_id, token, 95, "Storing audit report...")
                report_payload = {
                    "user_id": user_id,
                    "file_name": file_name,
                    "overall_risk_score": result.summary.overall_risk_score,
                    "summary_json": result.summary.model_dump(),
                    "clauses_json": [c.model_dump() for c in result.clauses]
                }
                if workspace_id:
                    report_payload["workspace_id"] = workspace_id

                rep_res = self.supabase.table("contract_reports").insert(report_payload).execute()
                if rep_res.data and len(rep_res.data) > 0:
                    report_id = rep_res.data[0]["id"]

                    # Persist Vector Embeddings
                    emb_rows = []
                    for idx, (clause, emb) in enumerate(zip(result.clauses, embeddings)):
                        emb_rows.append({
                            "report_id": report_id,
                            "user_id": user_id,
                            "workspace_id": workspace_id,
                            "clause_number": clause.clause_number,
                            "clause_text": clause.original_text,
                            "embedding": emb
                        })

                    if emb_rows:
                        self.supabase.table("contract_embeddings").insert(emb_rows).execute()

            # Step 5: Mark Completed via Fenced Stored Procedure
            completed = self._complete_job(job_id, token, report_id)
            if not completed:
                logger.warning(f"Worker {self.worker_id} lost lease on job {job_id}. Fencing token check aborted commit.")
                return False

            return True
        except Exception as e:
            sanitized_err = f"Analysis error: {str(e)[:200]}"
            self._fail_job(job_id, token, sanitized_err)
            return False

    def claim_and_run_one(self) -> Optional[bool]:
        """Claims a single queued job via PostgreSQL SKIP LOCKED and executes it."""
        if not self.supabase:
            return None

        try:
            res = self.supabase.rpc("claim_next_analysis_job", {
                "p_worker_id": self.worker_id
            }).execute()

            job_data = res.data
            if not job_data:
                return None  # No jobs claimable

            # Run in asyncio loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule as task
                asyncio.create_task(self.execute_job(job_data))
                return True
            else:
                return loop.run_until_complete(self.execute_job(job_data))
        except Exception as e:
            logger.error(f"Error in worker claim cycle: {e}")
            return False

    def _update_progress(self, job_id: str, token: int, progress: int, stage: str) -> bool:
        try:
            res = self.supabase.rpc("update_job_progress", {
                "p_job_id": job_id,
                "p_token": token,
                "p_progress": progress,
                "p_stage": stage
            }).execute()
            return bool(res.data)
        except Exception:
            return False

    def _complete_job(self, job_id: str, token: int, report_id: Optional[str]) -> bool:
        try:
            res = self.supabase.rpc("complete_analysis_job", {
                "p_job_id": job_id,
                "p_token": token,
                "p_report_id": report_id
            }).execute()
            return bool(res.data)
        except Exception:
            return False

    def _fail_job(self, job_id: str, token: int, error_msg: str) -> bool:
        try:
            res = self.supabase.rpc("fail_analysis_job", {
                "p_job_id": job_id,
                "p_token": token,
                "p_error_msg": error_msg
            }).execute()
            return bool(res.data)
        except Exception:
            return False

