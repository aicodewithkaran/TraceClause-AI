import threading
import pytest
from app.services.ai_budget_service import AIBudgetService, MODEL_PRICING

class MockBudgetDatabase:
    """
    In-memory simulation of the PostgreSQL database tables and stored procedures
    defined in supabase/migrations/20261118_durable_ai_budget_and_fenced_cleanup.sql.
    Thread-safe to test concurrency and race condition prevention.
    """
    def __init__(self, cap_microdollars: int = 250_000_000):
        self.lock = threading.Lock()
        self.cap_microdollars = cap_microdollars
        # Table: ai_budget_periods: key=(scope, month) -> dict
        self.budget_periods = {}
        # Table: ai_usage_reservations: key=reservation_id -> dict
        self.reservations = {}

    def reserve_ai_budget(self, p_reservation_id: str, p_estimated_microdollars: int,
                          p_provider: str, p_model: str, p_job_id: str = None,
                          p_scope: str = "global", p_cap_microdollars: int = None,
                          month: str = "2026-11") -> dict:
        with self.lock:
            # 1. Idempotency Check
            if p_reservation_id in self.reservations:
                return {
                    "success": True,
                    "status": "already_reserved",
                    "reservation_id": p_reservation_id,
                    "period_month": self.reservations[p_reservation_id]["period_month"]
                }

            cap = p_cap_microdollars if p_cap_microdollars is not None else self.cap_microdollars

            # 2. Lock or Initialize Budget Period Row
            period_key = (p_scope, month)
            if period_key not in self.budget_periods:
                self.budget_periods[period_key] = {
                    "scope": p_scope,
                    "period_month": month,
                    "cap_microdollars": cap,
                    "actual_spend_microdollars": 0,
                    "reserved_spend_microdollars": 0
                }
            period = self.budget_periods[period_key]

            # 3. Check Cap: actual + reserved + requested <= cap
            projected = period["actual_spend_microdollars"] + period["reserved_spend_microdollars"] + p_estimated_microdollars
            if projected > period["cap_microdollars"]:
                return {
                    "success": False,
                    "error": "BUDGET_EXCEEDED",
                    "cap_microdollars": period["cap_microdollars"],
                    "actual_spend_microdollars": period["actual_spend_microdollars"],
                    "reserved_spend_microdollars": period["reserved_spend_microdollars"],
                    "requested_microdollars": p_estimated_microdollars
                }

            # 4. Increment reserved spend
            period["reserved_spend_microdollars"] += p_estimated_microdollars

            # 5. Insert reservation
            self.reservations[p_reservation_id] = {
                "reservation_id": p_reservation_id,
                "scope": p_scope,
                "period_month": month,
                "provider": p_provider,
                "model": p_model,
                "estimated_microdollars": p_estimated_microdollars,
                "actual_microdollars": None,
                "status": "reserved"
            }

            return {
                "success": True,
                "status": "reserved",
                "reservation_id": p_reservation_id,
                "period_month": month
            }

    def settle_ai_budget(self, p_reservation_id: str, p_actual_microdollars: int,
                         p_status: str = "settled", p_metadata: dict = None) -> dict:
        with self.lock:
            if p_reservation_id not in self.reservations:
                return {"success": False, "error": "RESERVATION_NOT_FOUND"}

            res = self.reservations[p_reservation_id]
            # Idempotency check: if already settled or released, do not alter spend twice
            if res["status"] in ("settled", "released", "uncertain"):
                return {"success": True, "status": "already_settled", "current_status": res["status"]}

            period_key = (res["scope"], res["period_month"])
            period = self.budget_periods[period_key]

            # Decrement reserved, increment actual
            period["reserved_spend_microdollars"] = max(0, period["reserved_spend_microdollars"] - res["estimated_microdollars"])
            period["actual_spend_microdollars"] += p_actual_microdollars

            res["status"] = p_status
            res["actual_microdollars"] = p_actual_microdollars
            return {"success": True, "status": p_status, "actual_microdollars": p_actual_microdollars}

    def release_ai_budget(self, p_reservation_id: str, p_reason: str = "cancelled") -> dict:
        with self.lock:
            if p_reservation_id not in self.reservations:
                return {"success": False, "error": "RESERVATION_NOT_FOUND"}

            res = self.reservations[p_reservation_id]
            if res["status"] != "reserved":
                return {"success": True, "status": "already_resolved", "current_status": res["status"]}

            period_key = (res["scope"], res["period_month"])
            period = self.budget_periods[period_key]

            # Release reserved spend
            period["reserved_spend_microdollars"] = max(0, period["reserved_spend_microdollars"] - res["estimated_microdollars"])
            res["status"] = "released"
            return {"success": True, "status": "released"}


class MockSupabaseClient:
    def __init__(self, db: MockBudgetDatabase):
        self.db = db

    def rpc(self, name: str, params: dict):
        class RPCResult:
            def __init__(self, data):
                self.data = data
            def execute(self):
                return self

        if name == "reserve_ai_budget":
            data = self.db.reserve_ai_budget(**params)
            return RPCResult(data)
        elif name == "settle_ai_budget":
            data = self.db.settle_ai_budget(**params)
            return RPCResult(data)
        elif name == "release_ai_budget":
            data = self.db.release_ai_budget(**params)
            return RPCResult(data)
        raise NotImplementedError(f"RPC {name} not implemented")


def test_concurrent_requests_near_cap_never_exceed_budget():
    """Assert multiple concurrent requests near budget cap cannot race past the ceiling."""
    # Cap: 100,000 microdollars ($0.10)
    db = MockBudgetDatabase(cap_microdollars=100_000)
    client = MockSupabaseClient(db)
    service = AIBudgetService(supabase=client)
    service.cap_microdollars = 100_000

    results = []
    # 10 concurrent threads each trying to reserve 20,000 microdollars ($0.02)
    # Total available = 100,000 => exactly 5 should succeed, 5 must be rejected
    def worker_attempt(idx):
        success = service.reserve(
            reservation_id=f"req_thread_{idx}",
            estimated_microdollars=20_000,
            provider="gemini",
            model="gemini-1.5-pro"
        )
        results.append(success)

    threads = [threading.Thread(target=worker_attempt, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    success_count = sum(1 for r in results if r is True)
    failure_count = sum(1 for r in results if r is False)

    assert success_count == 5
    assert failure_count == 5

    # Check database state: reserved is exactly at 100,000
    period = db.budget_periods[("global", "2026-11")]
    assert period["reserved_spend_microdollars"] == 100_000
    assert period["actual_spend_microdollars"] == 0


def test_multiple_processes_sharing_same_cap():
    """Assert multiple service instances (simulating separate API/worker processes) share the exact same ledger."""
    db = MockBudgetDatabase(cap_microdollars=50_000)
    proc1 = AIBudgetService(supabase=MockSupabaseClient(db))
    proc2 = AIBudgetService(supabase=MockSupabaseClient(db))
    proc1.cap_microdollars = 50_000
    proc2.cap_microdollars = 50_000

    # Process 1 reserves 30,000
    assert proc1.reserve("req_p1", 30_000, "openai", "gpt-4o") is True

    # Process 2 attempts to reserve 30,000 -> rejected because 30,000 + 30,000 > 50,000
    assert proc2.reserve("req_p2", 30_000, "openai", "gpt-4o") is False

    # Process 2 attempts to reserve 20,000 -> allowed (30,000 + 20,000 == 50,000)
    assert proc2.reserve("req_p2_small", 20_000, "openai", "gpt-4o") is True


def test_restart_preserves_recorded_spend():
    """Assert database spend remains intact across process reboots."""
    db = MockBudgetDatabase(cap_microdollars=100_000)
    service1 = AIBudgetService(supabase=MockSupabaseClient(db))
    service1.cap_microdollars = 100_000

    service1.reserve("req_reboot_1", 40_000, "gemini", "gemini-1.5-pro")
    service1.settle("req_reboot_1", 35_000, status="settled")

    # Simulate restart by instantiating new service pointing to same database
    service2 = AIBudgetService(supabase=MockSupabaseClient(db))
    service2.cap_microdollars = 100_000

    period = db.budget_periods[("global", "2026-11")]
    assert period["actual_spend_microdollars"] == 35_000
    assert period["reserved_spend_microdollars"] == 0

    # Next reservation respects previous actual spend
    assert service2.reserve("req_reboot_2", 70_000, "gemini", "gemini-1.5-pro") is False  # 35k + 70k > 100k
    assert service2.reserve("req_reboot_3", 65_000, "gemini", "gemini-1.5-pro") is True   # 35k + 65k == 100k


def test_duplicate_settle_and_release_idempotent():
    """Assert duplicate settle or release calls do not mutate spend twice."""
    db = MockBudgetDatabase(cap_microdollars=100_000)
    service = AIBudgetService(supabase=MockSupabaseClient(db))
    service.cap_microdollars = 100_000

    service.reserve("req_idem_1", 20_000, "gemini", "gemini-1.5-pro")
    assert db.budget_periods[("global", "2026-11")]["reserved_spend_microdollars"] == 20_000

    # First settle
    assert service.settle("req_idem_1", 15_000, status="settled") is True
    period = db.budget_periods[("global", "2026-11")]
    assert period["actual_spend_microdollars"] == 15_000
    assert period["reserved_spend_microdollars"] == 0

    # Duplicate settle must not add to actual spend again
    assert service.settle("req_idem_1", 15_000, status="settled") is True
    assert period["actual_spend_microdollars"] == 15_000

    # Release on already settled must not alter spend
    assert service.release("req_idem_1") is True
    assert period["actual_spend_microdollars"] == 15_000


def test_provider_timeout_recorded_as_uncertain():
    """Assert provider timeout records estimated cost as uncertain spend so budget is not under-counted."""
    db = MockBudgetDatabase(cap_microdollars=100_000)
    service = AIBudgetService(supabase=MockSupabaseClient(db))
    service.cap_microdollars = 100_000

    service.reserve("req_timeout_1", 25_000, "openai", "gpt-4o")

    # On timeout, settle at estimated cost with status='uncertain'
    service.settle("req_timeout_1", 25_000, status="uncertain", metadata={"error": "ReadTimeout"})

    period = db.budget_periods[("global", "2026-11")]
    assert period["actual_spend_microdollars"] == 25_000
    assert period["reserved_spend_microdollars"] == 0

    res_row = db.reservations["req_timeout_1"]
    assert res_row["status"] == "uncertain"
    assert res_row["actual_microdollars"] == 25_000


def test_month_boundary_transition():
    """Assert a new month creates a new budget period without wiping prior month records."""
    db = MockBudgetDatabase(cap_microdollars=100_000)
    
    # November spend
    db.reserve_ai_budget("req_nov_1", 80_000, "gemini", "gemini-1.5-pro", month="2026-11")
    db.settle_ai_budget("req_nov_1", 80_000)

    # In November, remaining is 20k
    res_nov = db.reserve_ai_budget("req_nov_2", 30_000, "gemini", "gemini-1.5-pro", month="2026-11")
    assert res_nov["success"] is False

    # In December, a fresh budget period is initialized
    res_dec = db.reserve_ai_budget("req_dec_1", 50_000, "gemini", "gemini-1.5-pro", month="2026-12")
    assert res_dec["success"] is True

    # November data is preserved
    assert db.budget_periods[("global", "2026-11")]["actual_spend_microdollars"] == 80_000
    assert db.budget_periods[("global", "2026-12")]["reserved_spend_microdollars"] == 50_000
