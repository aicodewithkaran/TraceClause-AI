import os
import sys
import time
import asyncio
import signal
import logging
from typing import Set
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
    - Runs independently of the FastAPI web process.
    - Enforces bounded concurrency (default 4 concurrent jobs).
    - Periodic heartbeat & orphan job reclamation janitor.
    - Graceful shutdown handling on SIGINT/SIGTERM.
    """

    def __init__(self, concurrency_limit: int = 4):
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
        logger.info("Shutdown signal received. Finishing in-flight jobs before exiting...")
        self.running = False

    async def reclaim_orphaned_jobs(self):
        """
        Janitor: finds jobs stuck in 'processing' whose heartbeat has not been updated
        in > 5 minutes (indicating an abruptly killed worker container) and reclaims them.
        """
        if not self.supabase:
            return

        now = time.time()
        if now - self.last_janitor_run < 60:  # Run once every 60 seconds
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
                    logger.warning(f"Orphaned job {job_id} exceeded max retries ({retries}/{max_retries}). Failing.")
                    self.supabase.rpc("fail_analysis_job", {
                        "p_job_id": job_id,
                        "p_token": token,
                        "p_error_msg": "Job execution timed out after multiple worker interruptions."
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

    async def run(self):
        self.setup_signal_handlers()
        logger.info(f"TraceClause Worker Daemon started with concurrency limit = {self.concurrency_limit}")

        while self.running:
            # 1. Purge completed tasks from task set
            self.active_tasks = {t for t in self.active_tasks if not t.done()}

            # 2. Run orphan janitor
            await self.reclaim_orphaned_jobs()

            # 3. If under concurrency limit, attempt to claim next job
            if len(self.active_tasks) < self.concurrency_limit:
                try:
                    claim_res = self.worker.claim_and_run_one()
                    if claim_res:
                        continue
                except Exception as e:
                    logger.error(f"Worker claim error: {e}")

            # Sleep briefly to avoid tight polling loop
            await asyncio.sleep(1.0)

        # Graceful shutdown: wait for active tasks
        if self.active_tasks:
            logger.info(f"Waiting for {len(self.active_tasks)} in-flight tasks to conclude...")
            await asyncio.gather(*self.active_tasks, return_exceptions=True)

        logger.info("TraceClause Worker Daemon shut down cleanly.")

def main():
    concurrency = int(os.environ.get("WORKER_CONCURRENCY", "4"))
    daemon = SupervisedWorkerDaemon(concurrency_limit=concurrency)
    asyncio.run(daemon.run())

if __name__ == "__main__":
    main()

