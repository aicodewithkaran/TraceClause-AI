-- ==============================================================================
-- TRACECLAUSE AI v2 — MASTER DATABASE SCHEMA & PRODUCTION HARDENING
-- Completely idempotent: safe to run repeatedly in Supabase SQL Editor.
-- ==============================================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ==============================================================================
-- 2. MASTER TABLES DEFINITIONS
-- ==============================================================================

-- 2.1 User Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT NOT NULL,
  country TEXT NOT NULL,
  profession TEXT NOT NULL,
  phone_number TEXT,
  subscription_tier TEXT DEFAULT 'free' CHECK (subscription_tier IN ('free', 'solo', 'team')),
  lifetime_free_audits_used INT DEFAULT 0,
  monthly_quota_used INT DEFAULT 0,
  last_quota_reset TIMESTAMPTZ DEFAULT NOW(),
  subscription_expires_at TIMESTAMPTZ,
  tos_accepted_at TIMESTAMPTZ,
  tos_accepted_version TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMPTZ;

-- 2.2 Workspaces Table
CREATE TABLE IF NOT EXISTS public.workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  seat_limit INT DEFAULT 4,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.3 Workspace Members Table
CREATE TABLE IF NOT EXISTS public.workspace_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('owner', 'member')) DEFAULT 'member',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, user_id)
);

-- 2.4 Contract Reports Table
CREATE TABLE IF NOT EXISTS public.contract_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL,
  file_name TEXT NOT NULL,
  overall_risk_score TEXT NOT NULL,
  summary_json JSONB NOT NULL,
  clauses_json JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.5 Contract Embeddings Table
CREATE TABLE IF NOT EXISTS public.contract_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID NOT NULL REFERENCES public.contract_reports(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL,
  clause_number INT NOT NULL,
  clause_text TEXT NOT NULL,
  embedding vector(1536)
);

-- 2.6 Quota Reservations Table
CREATE TABLE IF NOT EXISTS public.quota_reservations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  target_profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  audit_id UUID NOT NULL UNIQUE,
  tier TEXT NOT NULL,
  status TEXT CHECK (status IN ('reserved', 'completed', 'committed', 'released')) DEFAULT 'reserved',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_quota_reservations_audit_id'
  ) THEN
    ALTER TABLE public.quota_reservations ADD CONSTRAINT uq_quota_reservations_audit_id UNIQUE (audit_id);
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END $$;

-- 2.7 Processed Webhooks Table
CREATE TABLE IF NOT EXISTS public.processed_webhooks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE NOT NULL,
  event_type TEXT NOT NULL,
  provider TEXT DEFAULT 'razorpay',
  payload JSONB,
  processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.8 Purchases Table (Authoritative Backend Razorpay Orders & Entitlements)
CREATE TABLE IF NOT EXISTS public.purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  plan_tier TEXT NOT NULL CHECK (plan_tier IN ('solo', 'team')),
  amount_cents INT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed', 'refunded')) DEFAULT 'pending',
  razorpay_order_id TEXT UNIQUE NOT NULL,
  razorpay_payment_id TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_purchases_order_id ON public.purchases(razorpay_order_id);
CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON public.purchases(user_id);

-- 2.9 Contract Analysis Jobs Table (Durable Queue with Fencing Tokens)
CREATE TABLE IF NOT EXISTS public.contract_analysis_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL,
  audit_reservation_id UUID NOT NULL UNIQUE,
  file_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')) DEFAULT 'queued',
  progress_percent INT DEFAULT 0,
  stage_message TEXT DEFAULT 'Job queued for processing...',
  retain_audit BOOLEAN DEFAULT TRUE,
  report_id UUID REFERENCES public.contract_reports(id) ON DELETE SET NULL,
  error_message TEXT,
  fencing_token INT DEFAULT 1,
  locked_by TEXT,
  locked_at TIMESTAMPTZ,
  heartbeat_at TIMESTAMPTZ,
  retry_count INT DEFAULT 0,
  max_retries INT DEFAULT 3,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_claimable 
  ON public.contract_analysis_jobs(status, retry_count) 
  WHERE status IN ('queued', 'processing');

CREATE INDEX IF NOT EXISTS idx_jobs_user_active 
  ON public.contract_analysis_jobs(user_id) 
  WHERE status IN ('queued', 'processing');

-- 2.10 Staged Job Payloads Table (Temporary Contract Text Storage with 2h Janitor Purge)
CREATE TABLE IF NOT EXISTS public.staged_job_payloads (
  job_id UUID PRIMARY KEY REFERENCES public.contract_analysis_jobs(id) ON DELETE CASCADE,
  extracted_text TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 3. ENABLE ROW LEVEL SECURITY (RLS) ON ALL TABLES
-- ==============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contract_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contract_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quota_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processed_webhooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contract_analysis_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.staged_job_payloads ENABLE ROW LEVEL SECURITY;

-- ==============================================================================
-- 4. TABLE-LEVEL PERMISSION REVOCATION & GRANULAR COLUMN GRANTS
-- ==============================================================================
REVOKE ALL ON TABLE public.profiles FROM anon, authenticated, public;
GRANT SELECT ON TABLE public.profiles TO authenticated;
GRANT UPDATE (full_name, country, profession, phone_number) ON TABLE public.profiles TO authenticated;

REVOKE ALL ON TABLE public.purchases FROM anon, authenticated, public;
GRANT SELECT ON TABLE public.purchases TO authenticated;

REVOKE ALL ON TABLE public.quota_reservations FROM anon, authenticated, public;
GRANT SELECT ON TABLE public.quota_reservations TO authenticated;

REVOKE ALL ON TABLE public.contract_analysis_jobs FROM anon, authenticated, public;
GRANT SELECT ON TABLE public.contract_analysis_jobs TO authenticated;

REVOKE ALL ON TABLE public.processed_webhooks FROM anon, authenticated, public;
REVOKE ALL ON TABLE public.staged_job_payloads FROM anon, authenticated, public;

-- ==============================================================================
-- 5. DYNAMIC PURGE OF ALL LEGACY RLS POLICIES
-- ==============================================================================
DO $$
DECLARE
  pol RECORD;
BEGIN
  FOR pol IN 
    SELECT policyname, tablename 
    FROM pg_policies 
    WHERE schemaname = 'public' 
      AND tablename IN (
        'profiles', 'workspaces', 'workspace_members', 'contract_reports', 
        'contract_embeddings', 'quota_reservations', 'processed_webhooks', 
        'purchases', 'contract_analysis_jobs', 'staged_job_payloads'
      )
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', pol.policyname, pol.tablename);
  END LOOP;
END $$;

-- ==============================================================================
-- 6. GRANULAR ROW LEVEL SECURITY POLICIES
-- ==============================================================================

-- 6.1 Profiles Policies
CREATE POLICY "profiles_select_policy" ON public.profiles
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "profiles_update_policy" ON public.profiles
  FOR UPDATE USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

CREATE POLICY "profiles_insert_policy" ON public.profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

-- 6.2 Workspaces Policies
CREATE POLICY "workspaces_select_policy" ON public.workspaces
  FOR SELECT USING (
    auth.uid() = owner_id OR 
    EXISTS (
      SELECT 1 FROM public.workspace_members wm 
      WHERE wm.workspace_id = public.workspaces.id AND wm.user_id = auth.uid()
    )
  );

CREATE POLICY "workspaces_owner_manage_policy" ON public.workspaces
  FOR ALL USING (auth.uid() = owner_id) WITH CHECK (auth.uid() = owner_id);

-- 6.3 Workspace Members Policies
CREATE POLICY "workspace_members_select_policy" ON public.workspace_members
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.workspace_members wm 
      WHERE wm.workspace_id = public.workspace_members.workspace_id AND wm.user_id = auth.uid()
    )
  );

CREATE POLICY "workspace_members_owner_manage_policy" ON public.workspace_members
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.workspaces w 
      WHERE w.id = public.workspace_members.workspace_id AND w.owner_id = auth.uid()
    )
  );

-- 6.4 Contract Reports Policies
CREATE POLICY "contract_reports_select_policy" ON public.contract_reports
  FOR SELECT USING (
    auth.uid() = user_id OR (
      workspace_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.workspace_members wm 
        WHERE wm.workspace_id = public.contract_reports.workspace_id 
          AND wm.user_id = auth.uid()
      )
    )
  );

CREATE POLICY "contract_reports_insert_policy" ON public.contract_reports
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "contract_reports_update_policy" ON public.contract_reports
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "contract_reports_delete_policy" ON public.contract_reports
  FOR DELETE USING (auth.uid() = user_id);

-- 6.5 Contract Embeddings Policies
CREATE POLICY "contract_embeddings_select_policy" ON public.contract_embeddings
  FOR SELECT USING (
    auth.uid() = user_id OR (
      workspace_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.workspace_members wm 
        WHERE wm.workspace_id = public.contract_embeddings.workspace_id 
          AND wm.user_id = auth.uid()
      )
    )
  );

CREATE POLICY "contract_embeddings_mutation_policy" ON public.contract_embeddings
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- 6.6 Purchases Policies
CREATE POLICY "purchases_select_policy" ON public.purchases
  FOR SELECT USING (auth.uid() = user_id);

-- 6.7 Contract Analysis Jobs Policies
CREATE POLICY "jobs_select_policy" ON public.contract_analysis_jobs
  FOR SELECT USING (auth.uid() = user_id);

-- 6.8 Quota Reservations Policies
CREATE POLICY "quota_reservations_select_policy" ON public.quota_reservations
  FOR SELECT USING (auth.uid() = user_id);

-- ==============================================================================
-- 7. SECURED STORED PROCEDURES
-- ==============================================================================

-- 7.1 Single-Transaction Atomic Purchase Fulfillment
CREATE OR REPLACE FUNCTION public.fulfill_purchase(
  p_order_id TEXT,
  p_payment_id TEXT,
  p_amount_cents INT,
  p_currency TEXT,
  p_event_id TEXT DEFAULT NULL,
  p_event_type TEXT DEFAULT 'payment.captured'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_purchase public.purchases%ROWTYPE;
  v_user_name TEXT;
  v_workspace_id UUID;
BEGIN
  -- 1. Idempotency Check on Webhook Event ID
  IF p_event_id IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM public.processed_webhooks WHERE event_id = p_event_id) THEN
      RETURN jsonb_build_object('success', true, 'status', 'duplicate_ignored', 'order_id', p_order_id);
    END IF;
  END IF;

  -- 2. Lock Purchase Record by Server-Stored Razorpay Order ID
  SELECT * INTO v_purchase
  FROM public.purchases
  WHERE razorpay_order_id = p_order_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'error', 'PURCHASE_NOT_FOUND', 'order_id', p_order_id);
  END IF;

  -- 3. Handle Already Completed Purchase Safely
  IF v_purchase.status = 'completed' THEN
    IF v_purchase.razorpay_payment_id = p_payment_id 
       AND v_purchase.amount_cents = p_amount_cents 
       AND LOWER(v_purchase.currency) = LOWER(p_currency) THEN
      RETURN jsonb_build_object('success', true, 'status', 'already_completed', 'purchase_id', v_purchase.id);
    ELSE
      RETURN jsonb_build_object('success', false, 'error', 'PAYMENT_CONFLICT', 'message', 'Conflicting payment details for completed purchase');
    END IF;
  END IF;

  -- 4. Check Expected Pending Status
  IF v_purchase.status != 'pending' THEN
    RETURN jsonb_build_object('success', false, 'error', 'INVALID_STATUS', 'current_status', v_purchase.status);
  END IF;

  -- 5. Strict Amount & Currency Verification (Commits 'failed' status without rolling back)
  IF v_purchase.amount_cents != p_amount_cents OR LOWER(v_purchase.currency) != LOWER(p_currency) THEN
    UPDATE public.purchases 
    SET status = 'failed' 
    WHERE id = v_purchase.id;

    RETURN jsonb_build_object(
      'success', false, 
      'error', 'AMOUNT_CURRENCY_MISMATCH',
      'expected_amount', v_purchase.amount_cents,
      'received_amount', p_amount_cents,
      'expected_currency', v_purchase.currency,
      'received_currency', p_currency
    );
  END IF;

  -- 6. Record Sanitized Webhook Event (No raw PII payload stored)
  IF p_event_id IS NOT NULL THEN
    INSERT INTO public.processed_webhooks (event_id, event_type, provider, payload)
    VALUES (
      p_event_id, 
      p_event_type, 
      'razorpay', 
      jsonb_build_object(
        'order_id', p_order_id, 
        'payment_id', p_payment_id, 
        'amount_cents', p_amount_cents, 
        'currency', p_currency, 
        'processed_at', NOW()
      )
    )
    ON CONFLICT (event_id) DO NOTHING;
  END IF;

  -- 7. Mark Purchase Completed
  UPDATE public.purchases
  SET status = 'completed',
      razorpay_payment_id = p_payment_id,
      completed_at = NOW()
  WHERE id = v_purchase.id;

  -- 8. Activate Profile Entitlement (Preserves remaining days on early renewal)
  UPDATE public.profiles
  SET subscription_tier = v_purchase.plan_tier,
      monthly_quota_used = 0,
      subscription_expires_at = GREATEST(COALESCE(subscription_expires_at, NOW()), NOW()) + INTERVAL '30 days'
  WHERE id = v_purchase.user_id;

  -- 9. Workspace Provisioning for Team Tier
  IF v_purchase.plan_tier = 'team' THEN
    IF NOT EXISTS (SELECT 1 FROM public.workspaces WHERE owner_id = v_purchase.user_id) THEN
      SELECT full_name INTO v_user_name FROM public.profiles WHERE id = v_purchase.user_id;
      INSERT INTO public.workspaces (owner_id, name, seat_limit)
      VALUES (v_purchase.user_id, COALESCE(v_user_name, 'Team') || '''s Workspace', 4)
      RETURNING id INTO v_workspace_id;

      INSERT INTO public.workspace_members (workspace_id, user_id, role)
      VALUES (v_workspace_id, v_purchase.user_id, 'owner')
      ON CONFLICT DO NOTHING;
    END IF;
  END IF;

  RETURN jsonb_build_object('success', true, 'status', 'fulfilled', 'purchase_id', v_purchase.id, 'plan_tier', v_purchase.plan_tier);
END;
$$;

REVOKE ALL ON FUNCTION public.fulfill_purchase(TEXT, TEXT, INT, TEXT, TEXT, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.fulfill_purchase(TEXT, TEXT, INT, TEXT, TEXT, TEXT) TO service_role;

-- 7.2 Combined Atomic Quota Reservation + Concurrency + Job Creation
CREATE OR REPLACE FUNCTION public.create_contract_analysis_job(
  p_user_id UUID,
  p_file_name TEXT,
  p_extracted_text TEXT,
  p_audit_reservation_id UUID,
  p_workspace_id UUID DEFAULT NULL,
  p_retain_audit BOOLEAN DEFAULT TRUE
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_caller_profile public.profiles%ROWTYPE;
  v_target_profile_id UUID := p_user_id;
  v_effective_tier TEXT;
  v_tier_limit INT;
  v_current_usage INT;
  v_active_jobs INT;
  v_job_id UUID;
  v_owner_id UUID;
  v_owner_profile public.profiles%ROWTYPE;
BEGIN
  -- 1. Exclusively lock the caller profile row
  SELECT * INTO v_caller_profile
  FROM public.profiles
  WHERE id = p_user_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Caller profile % not found', p_user_id;
  END IF;

  -- 2. Concurrency Check: Maximum 2 active jobs per user
  SELECT COUNT(*) INTO v_active_jobs
  FROM public.contract_analysis_jobs
  WHERE user_id = p_user_id AND status IN ('queued', 'processing');

  IF v_active_jobs >= 2 THEN
    RAISE EXCEPTION 'Concurrency limit exceeded: maximum 2 active jobs permitted per user';
  END IF;

  -- 3. Resolve Target Profile & Team Pooling
  IF p_workspace_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.workspace_members 
      WHERE workspace_id = p_workspace_id AND user_id = p_user_id
    ) THEN
      RAISE EXCEPTION 'Access Denied: Not a member of the specified workspace';
    END IF;

    SELECT owner_id INTO v_owner_id
    FROM public.workspaces
    WHERE id = p_workspace_id;

    IF v_owner_id IS NOT NULL AND v_owner_id != p_user_id THEN
      v_target_profile_id := v_owner_id;
      SELECT * INTO v_owner_profile
      FROM public.profiles
      WHERE id = v_target_profile_id
      FOR UPDATE;

      IF v_owner_profile.subscription_tier != 'team' 
         OR (v_owner_profile.subscription_expires_at IS NOT NULL AND v_owner_profile.subscription_expires_at < NOW()) THEN
        RAISE EXCEPTION 'Team workspace owner subscription is expired or inactive. Audits suspended.';
      END IF;

      v_effective_tier := 'team';
      v_tier_limit := 100;
      v_current_usage := COALESCE(v_owner_profile.monthly_quota_used, 0);
    END IF;
  END IF;

  IF v_target_profile_id = p_user_id THEN
    v_effective_tier := COALESCE(LOWER(v_caller_profile.subscription_tier), 'free');
    IF v_effective_tier != 'free' 
       AND v_caller_profile.subscription_expires_at IS NOT NULL 
       AND v_caller_profile.subscription_expires_at < NOW() THEN
      v_effective_tier := 'free';
    END IF;

    IF v_effective_tier = 'solo' THEN
      v_tier_limit := 20;
      v_current_usage := COALESCE(v_caller_profile.monthly_quota_used, 0);
    ELSIF v_effective_tier = 'team' THEN
      v_tier_limit := 100;
      v_current_usage := COALESCE(v_caller_profile.monthly_quota_used, 0);
    ELSE
      v_tier_limit := 3;
      v_current_usage := COALESCE(v_caller_profile.lifetime_free_audits_used, 0);
    END IF;
  END IF;

  -- 4. Enforce Quota Ceiling
  IF v_current_usage >= v_tier_limit THEN
    RAISE EXCEPTION 'QUOTA_EXCEEDED: % audit limit reached (% of % used)', v_effective_tier, v_current_usage, v_tier_limit;
  END IF;

  -- 5. Atomically Increment Usage on Target Profile
  IF v_effective_tier = 'free' THEN
    UPDATE public.profiles
    SET lifetime_free_audits_used = COALESCE(lifetime_free_audits_used, 0) + 1
    WHERE id = v_target_profile_id;
  ELSE
    UPDATE public.profiles
    SET monthly_quota_used = COALESCE(monthly_quota_used, 0) + 1
    WHERE id = v_target_profile_id;
  END IF;

  -- 6. Insert Quota Reservation Record
  INSERT INTO public.quota_reservations (user_id, target_profile_id, audit_id, tier, status)
  VALUES (p_user_id, v_target_profile_id, p_audit_reservation_id, v_effective_tier, 'reserved');

  -- 7. Insert Analysis Job with Initial Fencing Token (1)
  INSERT INTO public.contract_analysis_jobs (
    user_id, workspace_id, audit_reservation_id, file_name, retain_audit, status, fencing_token
  ) VALUES (
    p_user_id, p_workspace_id, p_audit_reservation_id, p_file_name, p_retain_audit, 'queued', 1
  ) RETURNING id INTO v_job_id;

  -- 8. Stage Clean Extracted Text Payload
  INSERT INTO public.staged_job_payloads (job_id, extracted_text)
  VALUES (v_job_id, p_extracted_text);

  RETURN jsonb_build_object(
    'job_id', v_job_id,
    'audit_reservation_id', p_audit_reservation_id,
    'tier', v_effective_tier,
    'usage_after_reservation', v_current_usage + 1,
    'tier_limit', v_tier_limit
  );
END;
$$;

REVOKE ALL ON FUNCTION public.create_contract_analysis_job FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_contract_analysis_job TO service_role;

-- 7.3 Fenced Job Claim Procedure
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
    'extracted_text', v_text
  );
END;
$$;

REVOKE ALL ON FUNCTION public.claim_next_analysis_job FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_next_analysis_job TO service_role;

-- 7.4 Fenced Progress Update Procedure
CREATE OR REPLACE FUNCTION public.update_job_progress(
  p_job_id UUID, p_token INT, p_progress INT, p_stage TEXT
) 
RETURNS BOOLEAN 
LANGUAGE plpgsql 
SECURITY DEFINER 
SET search_path = public, pg_temp
AS $$
DECLARE
  v_updated INT;
BEGIN
  UPDATE public.contract_analysis_jobs
  SET progress_percent = p_progress,
      stage_message = p_stage,
      heartbeat_at = NOW(),
      updated_at = NOW()
  WHERE id = p_job_id AND fencing_token = p_token;
  
  GET DIAGNOSTICS v_updated = ROW_COUNT;
  RETURN v_updated > 0;
END;
$$;

REVOKE ALL ON FUNCTION public.update_job_progress FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.update_job_progress TO service_role;

-- 7.5 Fenced Job Completion Procedure
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
  UPDATE public.contract_analysis_jobs
  SET status = 'completed',
      report_id = p_report_id,
      progress_percent = 100,
      stage_message = 'Analysis complete',
      updated_at = NOW()
  WHERE id = p_job_id AND fencing_token = p_token
  RETURNING * INTO v_job;

  IF v_job.id IS NULL THEN
    RETURN FALSE;
  END IF;

  UPDATE public.quota_reservations
  SET status = 'committed'
  WHERE audit_id = v_job.audit_reservation_id;

  DELETE FROM public.staged_job_payloads WHERE job_id = p_job_id;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION public.complete_analysis_job FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_analysis_job TO service_role;

-- 7.6 Fenced Terminal Failure & Quota Rollback Procedure
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
BEGIN
  UPDATE public.contract_analysis_jobs
  SET status = 'failed',
      error_message = p_error_msg,
      stage_message = 'Analysis failed',
      updated_at = NOW()
  WHERE id = p_job_id AND fencing_token = p_token
  RETURNING * INTO v_job;

  IF v_job.id IS NULL THEN
    RETURN FALSE;
  END IF;

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

  DELETE FROM public.staged_job_payloads WHERE job_id = p_job_id;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION public.fail_analysis_job FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.fail_analysis_job TO service_role;

-- 7.7 Authorized Grounded Vector Search (Backend-Only Procedure)
CREATE OR REPLACE FUNCTION public.match_contract_clauses (
  query_embedding vector(1536),
  match_report_id UUID,
  requesting_user_id UUID,
  match_count INT DEFAULT 5,
  similarity_threshold FLOAT DEFAULT 0.50
)
RETURNS TABLE (
  clause_number INT,
  clause_text TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.contract_reports cr
    WHERE cr.id = match_report_id
      AND (
        cr.user_id = requesting_user_id
        OR (
          cr.workspace_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM public.workspace_members wm
            WHERE wm.workspace_id = cr.workspace_id
              AND wm.user_id = requesting_user_id
          )
        )
      )
  ) THEN
    RAISE EXCEPTION 'Access Denied: Caller is not authorized for report %', match_report_id;
  END IF;

  RETURN QUERY
  SELECT
    ce.clause_number,
    ce.clause_text,
    1 - (ce.embedding <=> query_embedding) AS similarity
  FROM public.contract_embeddings ce
  WHERE ce.report_id = match_report_id
    AND (1 - (ce.embedding <=> query_embedding)) >= similarity_threshold
  ORDER BY ce.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

REVOKE ALL ON FUNCTION public.match_contract_clauses FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_contract_clauses TO service_role;

-- 7.8 Canonical Terms of Service Acceptance RPC
CREATE OR REPLACE FUNCTION public.accept_terms_of_service(version_string TEXT)
RETURNS VOID 
LANGUAGE plpgsql 
SECURITY DEFINER 
SET search_path = public, pg_temp
AS $$
DECLARE
  v_canonical_version CONSTANT TEXT := '2026-09-04';
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Authentication required.';
  END IF;

  IF version_string IS DISTINCT FROM v_canonical_version THEN
    RAISE EXCEPTION 'Invalid Terms of Service version: %. Expected current version: %', version_string, v_canonical_version;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid()) THEN
    RAISE EXCEPTION 'User profile record does not exist for %', auth.uid();
  END IF;

  UPDATE public.profiles
  SET tos_accepted_at = NOW(),
      tos_accepted_version = v_canonical_version
  WHERE id = auth.uid();
END;
$$;

REVOKE ALL ON FUNCTION public.accept_terms_of_service(TEXT) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.accept_terms_of_service(TEXT) TO authenticated;

-- 7.9 Profile Protection Trigger (Defense-in-Depth)
CREATE OR REPLACE FUNCTION public.protect_profile_subscription_fields()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  IF current_setting('request.jwt.claim.role', true) IS DISTINCT FROM 'service_role' THEN
    IF NEW.subscription_tier IS DISTINCT FROM OLD.subscription_tier THEN
      RAISE EXCEPTION 'Forbidden: subscription_tier can only be updated by verified payment gateway.';
    END IF;
    IF NEW.lifetime_free_audits_used IS DISTINCT FROM OLD.lifetime_free_audits_used THEN
      RAISE EXCEPTION 'Forbidden: lifetime_free_audits_used cannot be altered directly.';
    END IF;
    IF NEW.monthly_quota_used IS DISTINCT FROM OLD.monthly_quota_used THEN
      RAISE EXCEPTION 'Forbidden: monthly_quota_used cannot be altered directly.';
    END IF;
    IF NEW.subscription_expires_at IS DISTINCT FROM OLD.subscription_expires_at THEN
      RAISE EXCEPTION 'Forbidden: subscription_expires_at cannot be altered directly.';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tr_protect_profile_subscription_fields ON public.profiles;
CREATE TRIGGER tr_protect_profile_subscription_fields
BEFORE UPDATE ON public.profiles
FOR EACH ROW
EXECUTE FUNCTION public.protect_profile_subscription_fields();

-- 7.10 Automatic Profile Creation Trigger on Auth Signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  INSERT INTO public.profiles (
    id,
    email,
    full_name,
    country,
    profession,
    subscription_tier,
    lifetime_free_audits_used,
    monthly_quota_used,
    created_at
  )
  VALUES (
    NEW.id,
    COALESCE(NEW.email, ''),
    COALESCE(NEW.raw_user_meta_data->>'full_name', 'User'),
    COALESCE(NEW.raw_user_meta_data->>'country', 'Global'),
    COALESCE(NEW.raw_user_meta_data->>'profession', 'Legal Professional'),
    'free',
    0,
    0,
    NOW()
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
