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

        if not settings.AI_PROCESSING_ENABLED:
            logger.warning(f"AI processing kill switch active. Failing job {job_id} and restoring quota.")
            self._fail_job(job_id, token, "AI analysis is temporarily paused for scheduled maintenance. Quota has been refunded.")
            return False

        # Active background heartbeat refresher: updates heartbeat_at every 15s during long analysis/embedding tasks
        stop_heartbeat = asyncio.Event()

        async def _heartbeat_loop():
            while not stop_heartbeat.is_set():
                try:
                    await asyncio.sleep(15)
                    if stop_heartbeat.is_set():
                        break
                    await asyncio.to_thread(self._touch_heartbeat, job_id, token)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Heartbeat tick error for job {job_id}: {e}")

        heartbeat_task = asyncio.create_task(_heartbeat_loop())

        try:
            # Step 1: Chunking (Progress: 20%)
            if not self._update_progress(job_id, token, 20, "Extracting and segmenting clauses..."):
                logger.warning(f"Aborting job {job_id}: lease lost at 20% progress update.")
                return False

            clauses = await asyncio.to_thread(ChunkingEngine.split_into_clauses, extracted_text)

            # Step 2: LLM Risk Analysis (Progress: 50%)
            if not self._update_progress(job_id, token, 50, "Evaluating legal risks and generating redlines..."):
                logger.warning(f"Aborting job {job_id}: lease lost at 50% progress update.")
                return False

            # Run analysis in threadpool to avoid blocking async event loop
            result = await asyncio.to_thread(
                self.analyzer.analyze_clauses, file_name, extracted_text, clauses
            )

            report_id = None
            if retain_audit:
                # Step 3: Embeddings Generation (Progress: 80%)
                if not self._update_progress(job_id, token, 80, "Indexing semantic vector embeddings..."):
                    logger.warning(f"Aborting job {job_id}: lease lost at 80% progress update.")
                    return False

                clause_texts = [c.original_text for c in result.clauses]
                embeddings = await asyncio.to_thread(
                    self.vector_store.generate_embeddings_batch, clause_texts
                )

                # Step 4: Persist Report (Progress: 95%)
                if not self._update_progress(job_id, token, 95, "Storing audit report..."):
                    logger.warning(f"Aborting job {job_id}: lease lost at 95% progress update.")
                    return False

                # Format embeddings payload for atomic PostgreSQL persistence
                emb_payload = []
                for idx, (clause, emb) in enumerate(zip(result.clauses, embeddings)):
                    emb_payload.append({
                        "clause_number": clause.clause_number,
                        "clause_text": clause.original_text,
                        "embedding": emb
                    })

                # Report payload with risk score, summary, and clause breakdown
                report_payload = {
                    "overall_risk_score": result.summary.overall_risk_score,
                    "summary_json": result.summary.model_dump(),
                    "clauses_json": [c.model_dump() for c in result.clauses]
                }

                # Step 5: Atomically Persist Report, Embeddings, and Complete Job via Fenced RPC
                persist_res = self.supabase.rpc("persist_analysis_report_and_complete", {
                    "p_job_id": job_id,
                    "p_token": token,
                    "p_report_payload": report_payload,
                    "p_embeddings_payload": emb_payload
                }).execute()

                res_data = persist_res.data or {}
                if not res_data.get("success"):
                    logger.warning(f"Worker {self.worker_id} lease lost on job {job_id} (token {token}). persist_analysis_report_and_complete aborted.")
                    return False

                logger.info(f"Job {job_id} successfully persisted report {res_data.get('report_id')} and completed under token {token}.")
                return True
        except Exception as e:
            raw_err = str(e)
            logger.error(f"Job {job_id} failed with error: {raw_err}")
            
            # Map into clean, user-facing error messages without leaking internals
            if "budget" in raw_err.lower():
                user_msg = "Monthly AI budget limit reached. Quota has been refunded to your account."
            elif "incomplete" in raw_err.lower() or "malformed" in raw_err.lower() or "lacked valid" in raw_err.lower():
                user_msg = "Contract analysis encountered malformed model output. Quota has been refunded. Please retry."
            elif "rate_limit" in raw_err.lower() or "429" in raw_err:
                user_msg = "AI provider capacity limit reached. Quota has been refunded. Please retry in 1 minute."
            elif "timeout" in raw_err.lower() or "timed out" in raw_err.lower():
                user_msg = "AI analysis request timed out. Quota has been refunded. Please retry."
            elif "circuit breaker" in raw_err.lower() or "paused" in raw_err.lower():
                user_msg = "AI analysis is currently paused for maintenance. Quota has been refunded."
            else:
                user_msg = "We were unable to complete analysis on this document. Quota has been refunded to your account."

            self._fail_job(job_id, token, user_msg)
            return False
        finally:
            # Terminate active background heartbeat loop cleanly
            stop_heartbeat.set()
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except (asyncio.CancelledError, Exception):
                pass

    def claim_job(self) -> Optional[Dict[str, Any]]:
        """Claims a single queued job via PostgreSQL SKIP LOCKED and returns its payload."""
        if not self.supabase:
            return None

        try:
            res = self.supabase.rpc("claim_next_analysis_job", {
                "p_worker_id": self.worker_id
            }).execute()
            data = res.data
            if data and "report_id" not in data:
                # Query linked report_id to support retry cleanup even on older DB schemas
                try:
                    chk = self.supabase.table("contract_analysis_jobs").select("report_id").eq("id", data["job_id"]).execute()
                    if chk.data and chk.data[0].get("report_id"):
                        data["report_id"] = chk.data[0]["report_id"]
                except Exception:
                    pass
            return data
        except Exception as e:
            logger.error(f"Error in claim_job: {e}")
            return None

    def claim_and_run_one(self) -> Optional[bool]:
        """Claims a single queued job and executes it."""
        job_data = self.claim_job()
        if not job_data:
            return None

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.execute_job(job_data))
            return True
        else:
            return loop.run_until_complete(self.execute_job(job_data))

    def _touch_heartbeat(self, job_id: str, token: int) -> bool:
        """Touches heartbeat timestamp in database to prevent active long jobs from getting reclaimed."""
        if not self.supabase:
            return False
        try:
            res = self.supabase.table("contract_analysis_jobs") \
                .update({"heartbeat_at": "NOW()"}) \
                .eq("id", job_id) \
                .eq("fencing_token", token) \
                .execute()
            return bool(res.data)
        except Exception:
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
        """
        Fenced terminal failure transition.
        Delegates 100% of report/embedding cleanup and quota release to the atomic fail_analysis_job RPC.
        ZERO Python-side unfenced deletions to eliminate races against newer worker attempts.
        """
        try:
            res = self.supabase.rpc("fail_analysis_job", {
                "p_job_id": job_id,
                "p_token": token,
                "p_error_msg": error_msg
            }).execute()
            success = bool(res.data)
            if not success:
                logger.warning(f"Worker {self.worker_id} lease lost on job {job_id} (token {token}). fail_analysis_job aborted.")
            return success
        except Exception as e:
            logger.error(f"Error executing fail_analysis_job RPC for job {job_id}: {e}")
            return False

