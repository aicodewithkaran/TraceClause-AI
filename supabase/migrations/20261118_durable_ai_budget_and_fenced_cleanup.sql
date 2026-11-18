-- ==============================================================================
-- TRACECLAUSE AI v2 — DURABLE AI BUDGET LEDGER & FENCED ATOMIC CLEANUP MIGRATION
-- Run this migration to establish:
-- 1. ai_budget_periods: Monthly durable cap, actual spend, and reserved spend (microdollars)
-- 2. ai_usage_reservations: Per-request AI usage reservation, settlement, and release ledger
-- 3. Stored procedures: reserve_ai_budget, settle_ai_budget, release_ai_budget
-- 4. Contract reports ownership: analysis_job_id and fencing_token columns
-- 5. Atomic, fenced fail_analysis_job and complete_analysis_job stored procedures
-- ==============================================================================

-- 1. AI Budget Periods Table (Integer microdollars: $1 USD = 1,000,000 microdollars)
CREATE TABLE IF NOT EXISTS public.ai_budget_periods (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scope TEXT NOT NULL DEFAULT 'global',
  period_month TEXT NOT NULL, -- Format: YYYY-MM
  cap_microdollars BIGINT NOT NULL DEFAULT 250000000, -- $250.00 USD in microdollars
  actual_spend_microdollars BIGINT NOT NULL DEFAULT 0,
  reserved_spend_microdollars BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(scope, period_month)
);

CREATE INDEX IF NOT EXISTS idx_budget_periods_scope_month ON public.ai_budget_periods(scope, period_month);

-- 2. AI Usage Reservations Table
CREATE TABLE IF NOT EXISTS public.ai_usage_reservations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reservation_id TEXT UNIQUE NOT NULL,
  scope TEXT NOT NULL DEFAULT 'global',
  period_month TEXT NOT NULL,
  job_id UUID REFERENCES public.contract_analysis_jobs(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  estimated_microdollars BIGINT NOT NULL,
  actual_microdollars BIGINT,
  status TEXT NOT NULL CHECK (status IN ('reserved', 'settled', 'released', 'uncertain')) DEFAULT 'reserved',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  settled_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ai_reservations_job_id ON public.ai_usage_reservations(job_id);
CREATE INDEX IF NOT EXISTS idx_ai_reservations_scope_month ON public.ai_usage_reservations(scope, period_month);

-- 3. Add analysis_job_id and fencing_token to contract_reports for strict ownership
ALTER TABLE public.contract_reports ADD COLUMN IF NOT EXISTS analysis_job_id UUID REFERENCES public.contract_analysis_jobs(id) ON DELETE SET NULL;
ALTER TABLE public.contract_reports ADD COLUMN IF NOT EXISTS fencing_token INT DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_contract_reports_job_token ON public.contract_reports(analysis_job_id, fencing_token);
CREATE UNIQUE INDEX IF NOT EXISTS uq_contract_reports_job_token ON public.contract_reports(analysis_job_id, fencing_token) WHERE analysis_job_id IS NOT NULL;

-- 4. Enable RLS on newly created tables
ALTER TABLE public.ai_budget_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_usage_reservations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.ai_budget_periods FROM anon, authenticated, public;
REVOKE ALL ON TABLE public.ai_usage_reservations FROM anon, authenticated, public;
GRANT SELECT ON TABLE public.ai_budget_periods TO service_role;
GRANT SELECT ON TABLE public.ai_usage_reservations TO service_role;

-- ==============================================================================
-- 5. ATOMIC STORED PROCEDURES FOR AI BUDGET
-- ==============================================================================

-- 5.1 Atomically Reserve AI Budget
CREATE OR REPLACE FUNCTION public.reserve_ai_budget(
  p_reservation_id TEXT,
  p_estimated_microdollars BIGINT,
  p_provider TEXT,
  p_model TEXT,
  p_job_id UUID DEFAULT NULL,
  p_scope TEXT DEFAULT 'global',
  p_cap_microdollars BIGINT DEFAULT 250000000
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_month TEXT := TO_CHAR(NOW() AT TIME ZONE 'UTC', 'YYYY-MM');
  v_budget public.ai_budget_periods%ROWTYPE;
  v_existing public.ai_usage_reservations%ROWTYPE;
BEGIN
  PERFORM set_config('app.internal_mutation', 'true', true);

  -- 1. Idempotency Check: if reservation_id already exists, return current status
  SELECT * INTO v_existing
  FROM public.ai_usage_reservations
  WHERE reservation_id = p_reservation_id;

  IF FOUND THEN
    RETURN jsonb_build_object(
      'success', true, 
      'status', 'already_reserved',
      'reservation_id', p_reservation_id,
      'period_month', v_existing.period_month
    );
  END IF;

  -- 2. Lock or Initialize Budget Period Row
  SELECT * INTO v_budget
  FROM public.ai_budget_periods
  WHERE scope = p_scope AND period_month = v_month
  FOR UPDATE;

  IF NOT FOUND THEN
    INSERT INTO public.ai_budget_periods (
      scope, period_month, cap_microdollars, actual_spend_microdollars, reserved_spend_microdollars
    ) VALUES (
      p_scope, v_month, p_cap_microdollars, 0, 0
    ) RETURNING * INTO v_budget;
  END IF;

  -- 3. Check Cap: (actual + reserved + requested) <= cap
  IF (v_budget.actual_spend_microdollars + v_budget.reserved_spend_microdollars + p_estimated_microdollars) > v_budget.cap_microdollars THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', 'BUDGET_EXCEEDED',
      'cap_microdollars', v_budget.cap_microdollars,
      'actual_spend_microdollars', v_budget.actual_spend_microdollars,
      'reserved_spend_microdollars', v_budget.reserved_spend_microdollars,
      'requested_microdollars', p_estimated_microdollars
    );
  END IF;

  -- 4. Atomically Increment Reserved Spend
  UPDATE public.ai_budget_periods
  SET reserved_spend_microdollars = reserved_spend_microdollars + p_estimated_microdollars,
      updated_at = NOW()
  WHERE id = v_budget.id;

  -- 5. Record Reservation Row
  INSERT INTO public.ai_usage_reservations (
    reservation_id, scope, period_month, job_id, provider, model, estimated_microdollars, status
  ) VALUES (
    p_reservation_id, p_scope, v_month, p_job_id, p_provider, p_model, p_estimated_microdollars, 'reserved'
  );

  RETURN jsonb_build_object(
    'success', true,
    'status', 'reserved',
    'reservation_id', p_reservation_id,
    'period_month', v_month
  );
END;
$$;

REVOKE ALL ON FUNCTION public.reserve_ai_budget FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reserve_ai_budget TO service_role;

-- 5.2 Atomically Settle AI Budget
CREATE OR REPLACE FUNCTION public.settle_ai_budget(
  p_reservation_id TEXT,
  p_actual_microdollars BIGINT,
  p_status TEXT DEFAULT 'settled',
  p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_res public.ai_usage_reservations%ROWTYPE;
BEGIN
  PERFORM set_config('app.internal_mutation', 'true', true);

  -- 1. Lock Reservation Row
  SELECT * INTO v_res
  FROM public.ai_usage_reservations
  WHERE reservation_id = p_reservation_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'error', 'RESERVATION_NOT_FOUND', 'reservation_id', p_reservation_id);
  END IF;

  -- 2. Idempotency Check: if already settled or released, return status
  IF v_res.status IN ('settled', 'released', 'uncertain') THEN
    RETURN jsonb_build_object('success', true, 'status', 'already_settled', 'current_status', v_res.status);
  END IF;

  -- 3. Lock Budget Period Row and Transfer Reserved to Actual
  UPDATE public.ai_budget_periods
  SET reserved_spend_microdollars = GREATEST(0, reserved_spend_microdollars - v_res.estimated_microdollars),
      actual_spend_microdollars = actual_spend_microdollars + p_actual_microdollars,
      updated_at = NOW()
  WHERE scope = v_res.scope AND period_month = v_res.period_month;

  -- 4. Mark Reservation Settled / Uncertain
  UPDATE public.ai_usage_reservations
  SET status = p_status,
      actual_microdollars = p_actual_microdollars,
      settled_at = NOW(),
      metadata = COALESCE(p_metadata, '{}'::jsonb)
  WHERE id = v_res.id;

  RETURN jsonb_build_object('success', true, 'status', p_status, 'actual_microdollars', p_actual_microdollars);
END;
$$;

REVOKE ALL ON FUNCTION public.settle_ai_budget FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.settle_ai_budget TO service_role;

-- 5.3 Atomically Release AI Budget (e.g. Unbillable Failure or Cancellation)
CREATE OR REPLACE FUNCTION public.release_ai_budget(
  p_reservation_id TEXT,
  p_reason TEXT DEFAULT 'cancelled'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_res public.ai_usage_reservations%ROWTYPE;
BEGIN
  PERFORM set_config('app.internal_mutation', 'true', true);

  -- 1. Lock Reservation Row
  SELECT * INTO v_res
  FROM public.ai_usage_reservations
  WHERE reservation_id = p_reservation_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'error', 'RESERVATION_NOT_FOUND', 'reservation_id', p_reservation_id);
  END IF;

  -- 2. Idempotency Check
  IF v_res.status != 'reserved' THEN
    RETURN jsonb_build_object('success', true, 'status', 'already_resolved', 'current_status', v_res.status);
  END IF;

  -- 3. Release Reserved Amount from Budget Period
  UPDATE public.ai_budget_periods
  SET reserved_spend_microdollars = GREATEST(0, reserved_spend_microdollars - v_res.estimated_microdollars),
      updated_at = NOW()
  WHERE scope = v_res.scope AND period_month = v_res.period_month;

  -- 4. Mark Reservation Released
  UPDATE public.ai_usage_reservations
  SET status = 'released',
      settled_at = NOW(),
      metadata = jsonb_build_object('release_reason', p_reason)
  WHERE id = v_res.id;

  RETURN jsonb_build_object('success', true, 'status', 'released');
END;
$$;

REVOKE ALL ON FUNCTION public.release_ai_budget FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.release_ai_budget TO service_role;

-- ==============================================================================
-- 6. REVISED FENCED FAILURE & COMPLETION STORED PROCEDURES
-- ==============================================================================

-- 6.1 Fenced Terminal Failure & Atomic Report Cleanup
CREATE OR REPLACE FUNCTION public.fail_analysis_job(
  p_job_id UUID, p_token INT, p_error_msg TEXT
) 
RETURNS BOOLEAN 
LANGUAGE plpgsql 
SECURITY DEFINER 
SET search_path = public, pg_temp
AS $$
DECLARE
  v_job public.contract_analysis_jobs%ROWTYPE;
  v_res public.quota_reservations%ROWTYPE;
  v_report_id UUID;
BEGIN
  PERFORM set_config('app.internal_mutation', 'true', true);

  -- 1. Exclusively select and lock the job requiring job_id, fencing_token, and status = 'processing'
  SELECT * INTO v_job
  FROM public.contract_analysis_jobs
  WHERE id = p_job_id AND fencing_token = p_token AND status = 'processing'
  FOR UPDATE;

  IF NOT FOUND THEN
    RETURN FALSE;  -- Stale worker or lease lost; abort safely without mutating anything
  END IF;

  -- 2. Locate linked partial report for this job attempt
  v_report_id := v_job.report_id;
  IF v_report_id IS NULL THEN
    SELECT id INTO v_report_id
    FROM public.contract_reports
    WHERE analysis_job_id = p_job_id AND fencing_token = p_token
    LIMIT 1;
  END IF;

  -- 3. Atomically delete embeddings and partial report
  IF v_report_id IS NOT NULL THEN
    DELETE FROM public.contract_embeddings WHERE report_id = v_report_id;
    DELETE FROM public.contract_reports WHERE id = v_report_id;
  END IF;

  -- Double-check direct job-token association
  DELETE FROM public.contract_embeddings WHERE report_id IN (
    SELECT id FROM public.contract_reports WHERE analysis_job_id = p_job_id AND fencing_token = p_token
  );
  DELETE FROM public.contract_reports WHERE analysis_job_id = p_job_id AND fencing_token = p_token;

  -- 4. Mark job failed and store sanitized error message
  UPDATE public.contract_analysis_jobs
  SET status = 'failed',
      report_id = NULL,
      error_message = p_error_msg,
      stage_message = 'Analysis failed',
      updated_at = NOW()
  WHERE id = p_job_id AND fencing_token = p_token;

  -- 5. Release quota reservation exactly once
  SELECT * INTO v_res 
  FROM public.quota_reservations 
  WHERE audit_id = v_job.audit_reservation_id AND status = 'reserved'
  FOR UPDATE;

  IF v_res.id IS NOT NULL THEN
    IF v_res.tier = 'free' THEN
      UPDATE public.profiles
      SET lifetime_free_audits_used = GREATEST(0, COALESCE(lifetime_free_audits_used, 1) - 1)
      WHERE id = v_res.target_profile_id;
    ELSE
      UPDATE public.profiles
      SET monthly_quota_used = GREATEST(0, COALESCE(monthly_quota_used, 1) - 1)
      WHERE id = v_res.target_profile_id;
    END IF;

    UPDATE public.quota_reservations SET status = 'released' WHERE id = v_res.id;
  END IF;

  -- 6. Purge staged contract text immediately
  DELETE FROM public.staged_job_payloads WHERE job_id = p_job_id;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION public.fail_analysis_job FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.fail_analysis_job TO service_role;

-- 6.2 Fenced Completion Procedure with Report Ownership Link
CREATE OR REPLACE FUNCTION public.complete_analysis_job(
  p_job_id UUID, p_token INT, p_report_id UUID
) 
RETURNS BOOLEAN 
LANGUAGE plpgsql 
SECURITY DEFINER 
SET search_path = public, pg_temp
AS $$
DECLARE
  v_job public.contract_analysis_jobs%ROWTYPE;
BEGIN
  PERFORM set_config('app.internal_mutation', 'true', true);

  UPDATE public.contract_analysis_jobs
  SET status = 'completed',
      report_id = p_report_id,
      progress_percent = 100,
      stage_message = 'Analysis complete',
      updated_at = NOW()
  WHERE id = p_job_id AND fencing_token = p_token AND status = 'processing'
  RETURNING * INTO v_job;

  IF v_job.id IS NULL THEN
    RETURN FALSE;  -- Lease lost; stale worker aborts safely without mutating anything
  END IF;

  -- Link report ownership to job_id and fencing_token
  IF p_report_id IS NOT NULL THEN
    UPDATE public.contract_reports
    SET analysis_job_id = p_job_id,
        fencing_token = p_token
    WHERE id = p_report_id;
  END IF;

  -- Commit quota reservation
  UPDATE public.quota_reservations
  SET status = 'committed'
  WHERE audit_id = v_job.audit_reservation_id;

  -- Purge staged contract text immediately
  DELETE FROM public.staged_job_payloads WHERE job_id = p_job_id;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION public.complete_analysis_job FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_analysis_job TO service_role;

-- 6.3 Fenced Job Claim Procedure with Atomic Abandoned Report Cleanup
CREATE OR REPLACE FUNCTION public.claim_next_analysis_job(p_worker_id TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_job public.contract_analysis_jobs%ROWTYPE;
  v_text TEXT;
BEGIN
  WITH claimable AS (
    SELECT id
    FROM public.contract_analysis_jobs
    WHERE (status = 'queued' AND retry_count < max_retries)
       OR (status = 'processing' AND heartbeat_at < NOW() - INTERVAL '2 minutes' AND retry_count < max_retries)
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  UPDATE public.contract_analysis_jobs j
  SET status = 'processing',
      fencing_token = j.fencing_token + 1,
      locked_by = p_worker_id,
      locked_at = NOW(),
      heartbeat_at = NOW(),
      retry_count = j.retry_count + 1,
      updated_at = NOW()
  FROM claimable
  WHERE j.id = claimable.id
  RETURNING j.* INTO v_job;

  IF v_job.id IS NULL THEN
    RETURN NULL;
  END IF;

  -- Atomic Retry Cleanup: If reclaiming an abandoned job, delete any partial report/embeddings from prior attempts
  IF v_job.report_id IS NOT NULL THEN
    DELETE FROM public.contract_embeddings WHERE report_id = v_job.report_id;
    DELETE FROM public.contract_reports WHERE id = v_job.report_id;
    UPDATE public.contract_analysis_jobs SET report_id = NULL WHERE id = v_job.id;
  END IF;

  DELETE FROM public.contract_embeddings WHERE report_id IN (
    SELECT id FROM public.contract_reports WHERE analysis_job_id = v_job.id
  );
  DELETE FROM public.contract_reports WHERE analysis_job_id = v_job.id;

  SELECT extracted_text INTO v_text
  FROM public.staged_job_payloads
  WHERE job_id = v_job.id;

  RETURN jsonb_build_object(
    'job_id', v_job.id,
    'fencing_token', v_job.fencing_token,
    'file_name', v_job.file_name,
    'user_id', v_job.user_id,
    'workspace_id', v_job.workspace_id,
    'retain_audit', v_job.retain_audit,
    'audit_reservation_id', v_job.audit_reservation_id,
    'report_id', NULL,
    'extracted_text', v_text
  );
END;
$$;

REVOKE ALL ON FUNCTION public.claim_next_analysis_job FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_next_analysis_job TO service_role;
