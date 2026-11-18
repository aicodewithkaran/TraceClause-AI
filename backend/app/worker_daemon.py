import os
import sys
import time
import asyncio
import signal
import logging
from typing import Set, Dict, Any
from app.core.config import settings
from app.services.job_worker import JobWorker
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [worker_daemon] %(message)s"
)
logger = logging.getLogger("worker_daemon")

class SupervisedWorkerDaemon:
    """
    Independent Supervised Background Worker Daemon for TraceClause AI.
    - Runs independently of the FastAPI web process (e.g., as a Render background worker).
    - Enforces bounded concurrency (1-2 concurrent jobs for beta launch safety).
    - Periodic heartbeat & orphan job reclamation janitor.
    - Graceful shutdown handling on SIGINT/SIGTERM, allowing in-flight jobs to finish cleanly.
    - Strict environment validation refusing to start if database or provider credentials are missing.
    """

    def __init__(self, concurrency_limit: int = 2):
        self.concurrency_limit = concurrency_limit
        self.running = True
        self.active_tasks: Set[asyncio.Task] = set()
        self.worker = JobWorker(worker_id=f"daemon_{os.getpid()}")
        self.last_janitor_run = 0.0

        if settings.SUPABASE_URL and settings.supabase_admin_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
        elif settings.SUPABASE_URL and settings.supabase_anon_key:
            self.supabase = create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
        else:
            self.supabase = None

    def setup_signal_handlers(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.initiate_shutdown)
            except (NotImplementedError, AttributeError):
                # Fallback for environments where signal handlers are restricted
                pass

    def initiate_shutdown(self):
        logger.info("Shutdown signal received. Initiating graceful shutdown; no new jobs will be claimed...")
        self.running = False

    async def reclaim_orphaned_jobs(self):
        """
        Janitor: finds jobs stuck in 'processing' whose heartbeat has not been updated
        in > 5 minutes (indicating an abruptly killed worker container) and reclaims them.
        """
        if not self.supabase:
            return

        now = time.time()
        if now - self.last_janitor_run < 60:  # Run at most once every 60 seconds
            return

        self.last_janitor_run = now
        try:
            cutoff = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now - 300))
            res = self.supabase.table("contract_analysis_jobs") \
                .select("id, retry_count, max_retries, audit_reservation_id, fencing_token") \
                .eq("status", "processing") \
                .lt("heartbeat_at", cutoff) \
                .execute()

            orphans = res.data or []
            for orphan in orphans:
                job_id = orphan["id"]
                retries = orphan.get("retry_count", 0)
                max_retries = orphan.get("max_retries", 3)
                token = orphan.get("fencing_token", 1)

                if retries >= max_retries:
                    logger.warning(f"Orphaned job {job_id} exceeded max retries ({retries}/{max_retries}). Failing and refunding quota.")
                    self.supabase.rpc("fail_analysis_job", {
                        "p_job_id": job_id,
                        "p_token": token,
                        "p_error_msg": "Job execution timed out after multiple worker interruptions. Quota refunded."
                    }).execute()
                else:
                    logger.info(f"Reclaiming orphaned job {job_id} (retry {retries + 1}/{max_retries}).")
                    self.supabase.table("contract_analysis_jobs") \
                        .update({
                            "status": "queued",
                            "locked_by": None,
                            "locked_at": None,
                            "retry_count": retries + 1,
                            "stage_message": f"Re-queued after worker timeout (retry {retries + 1})"
                        }) \
                        .eq("id", job_id) \
                        .execute()
        except Exception as e:
            logger.error(f"Error in orphan reclamation janitor: {e}")

    async def _execute_job_task(self, job_data: Dict[str, Any]):
        """Wraps job execution in a tracked task."""
        job_id = job_data.get("job_id")
        try:
            success = await self.worker.execute_job(job_data)
            logger.info(f"Job {job_id} completed with success={success}")
        except Exception as e:
            logger.error(f"Job {job_id} raised unhandled exception: {e}")

    async def run(self):
        # 1. Enforce environment and configuration validation
        settings.validate_worker_configuration()
        self.setup_signal_handlers()
        logger.info(f"TraceClause Supervised Worker Daemon initialized. Concurrency limit = {self.concurrency_limit}")

        while self.running:
            # 2. Cleanup completed tasks from active set
            self.active_tasks = {t for t in self.active_tasks if not t.done()}

            # 3. Run periodic orphan reclamation
            await self.reclaim_orphaned_jobs()

            # 4. Claim new jobs up to concurrency limit
            while self.running and len(self.active_tasks) < self.concurrency_limit:
                try:
                    job_data = self.worker.claim_job()
                    if not job_data:
                        break  # No claimable queued jobs
                    
                    job_id = job_data.get("job_id")
                    task = asyncio.create_task(self._execute_job_task(job_data), name=f"job-{job_id}")
                    self.active_tasks.add(task)
                    task.add_done_callback(self.active_tasks.discard)
                    logger.info(f"Claimed job {job_id}. Active worker tasks: {len(self.active_tasks)}/{self.concurrency_limit}")
                except Exception as e:
                    logger.error(f"Error claiming job from queue: {e}")
                    break

            # 5. Non-blocking sleep between poll iterations
            await asyncio.sleep(1.0)

        # Graceful shutdown: wait for all active tasks to finish
        if self.active_tasks:
            logger.info(f"Shutdown in progress. Waiting for {len(self.active_tasks)} active tasks to conclude...")
            await asyncio.gather(*self.active_tasks, return_exceptions=True)

        logger.info("TraceClause Worker Daemon shut down cleanly.")

def main():
    concurrency = int(os.environ.get("WORKER_CONCURRENCY", str(settings.WORKER_CONCURRENCY)))
    daemon = SupervisedWorkerDaemon(concurrency_limit=concurrency)
    asyncio.run(daemon.run())

if __name__ == "__main__":
    main()
