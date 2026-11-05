# ==============================================================================
# TRACECLAUSE AI v2 — CANONICAL BILLING CONFIGURATION & PLAN CATALOG
# Server-Authoritative: Clients cannot specify or tamper with amounts or currencies.
# ==============================================================================

PLAN_CATALOG = {
    "solo": {
        "name": "Solo Plan",
        "amount_cents": 7900,       # $79.00 USD
        "currency": "USD",
        "quota_audits": 20,
        "duration_days": 30
    },
    "team": {
        "name": "Team Plan",
        "amount_cents": 29900,      # $299.00 USD
        "currency": "USD",
        "quota_audits": 100,
        "duration_days": 30
    }
}

