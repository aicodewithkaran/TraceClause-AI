-- ==============================================================================
-- TRACECLAUSE AI v2 — MIGRATION: ATOMIC QUOTA LEDGER & RAZORPAY WEBHOOK IDEMPOTENCY
-- ==============================================================================

-- 1. Create Quota Reservations Ledger Table
CREATE TABLE IF NOT EXISTS public.quota_reservations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  target_profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  audit_id UUID NOT NULL,
  tier TEXT NOT NULL,
  status TEXT CHECK (status IN ('reserved', 'completed', 'released')) DEFAULT 'reserved',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quota_reservations_user_audit 
  ON public.quota_reservations(user_id, audit_id);

CREATE INDEX IF NOT EXISTS idx_quota_reservations_status 
  ON public.quota_reservations(status);

ALTER TABLE public.quota_reservations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own quota reservations" ON public.quota_reservations
  FOR SELECT USING (auth.uid() = user_id);

-- 2. Create Processed Webhooks Table for Idempotent Payment Event Processing
CREATE TABLE IF NOT EXISTS public.processed_webhooks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE NOT NULL,
  event_type TEXT NOT NULL,
  provider TEXT DEFAULT 'razorpay',
  payload JSONB,
  processed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_webhooks_event_id 
  ON public.processed_webhooks(event_id);

ALTER TABLE public.processed_webhooks ENABLE ROW LEVEL SECURITY;

-- 3. Stored Procedure: reserve_quota
-- Atomically checks quota against limits (with row locking) and creates a 'reserved' ledger entry
CREATE OR REPLACE FUNCTION public.reserve_quota(p_user_id UUID, p_audit_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_tier TEXT;
  v_lifetime_used INT;
  v_monthly_used INT;
  v_last_reset TIMESTAMPTZ;
  v_limit INT;
  v_target_profile_id UUID := p_user_id;
  v_workspace_id UUID;
  v_owner_id UUID;
  v_result JSONB;
BEGIN
  -- Row-lock caller profile to prevent race conditions
  SELECT subscription_tier, lifetime_free_audits_used, monthly_quota_used, last_quota_reset
  INTO v_tier, v_lifetime_used, v_monthly_used, v_last_reset
  FROM public.profiles
  WHERE id = p_user_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'USER_NOT_FOUND' USING ERRCODE = 'P0002';
  END IF;

  v_tier := COALESCE(LOWER(v_tier), 'free');

  -- Free Tier: 3 Lifetime Audits
  IF v_tier = 'free' THEN
    IF COALESCE(v_lifetime_used, 0) >= 3 THEN
      RAISE EXCEPTION 'QUOTA_EXCEEDED: Free trial limit reached (3/3 contracts)' USING ERRCODE = 'P0001';
    END IF;

    UPDATE public.profiles
    SET lifetime_free_audits_used = COALESCE(lifetime_free_audits_used, 0) + 1
    WHERE id = p_user_id;

    INSERT INTO public.quota_reservations(user_id, target_profile_id, audit_id, tier, status)
    VALUES (p_user_id, p_user_id, p_audit_id, 'free', 'reserved');

    SELECT jsonb_build_object(
      'quota_used', lifetime_free_audits_used,
      'limit', 3,
      'tier', 'free',
      'remaining', 3 - lifetime_free_audits_used
    ) INTO v_result
    FROM public.profiles
    WHERE id = p_user_id;

    RETURN v_result;
  END IF;

  -- Paid Tiers: Solo (20) or Team (100)
  IF v_tier = 'solo' THEN
    v_limit := 20;
  ELSIF v_tier = 'team' THEN
    v_limit := 100;
    -- Check if user is in a shared team workspace to pool usage under owner
    SELECT workspace_id INTO v_workspace_id
    FROM public.workspace_members
    WHERE user_id = p_user_id
    LIMIT 1;

    IF v_workspace_id IS NOT NULL THEN
      SELECT owner_id INTO v_owner_id
      FROM public.workspaces
      WHERE id = v_workspace_id;

      IF v_owner_id IS NOT NULL AND v_owner_id <> p_user_id THEN
        v_target_profile_id := v_owner_id;
        -- Lock owner profile
        SELECT subscription_tier, monthly_quota_used, last_quota_reset
        INTO v_tier, v_monthly_used, v_last_reset
        FROM public.profiles
        WHERE id = v_target_profile_id
        FOR UPDATE;
      END IF;
    END IF;
  ELSE
    v_limit := 3;
  END IF;

  -- 30-day reset check
  IF v_last_reset IS NULL OR NOW() > (v_last_reset + INTERVAL '30 days') THEN
    v_monthly_used := 0;
    UPDATE public.profiles
    SET monthly_quota_used = 0, last_quota_reset = NOW()
    WHERE id = v_target_profile_id;
  END IF;

  IF COALESCE(v_monthly_used, 0) >= v_limit THEN
    RAISE EXCEPTION 'QUOTA_EXCEEDED: Monthly contract review limit reached' USING ERRCODE = 'P0001';
  END IF;

  UPDATE public.profiles
  SET monthly_quota_used = COALESCE(monthly_quota_used, 0) + 1
  WHERE id = v_target_profile_id;

  INSERT INTO public.quota_reservations(user_id, target_profile_id, audit_id, tier, status)
  VALUES (p_user_id, v_target_profile_id, p_audit_id, v_tier, 'reserved');

  SELECT jsonb_build_object(
    'quota_used', monthly_quota_used,
    'limit', v_limit,
    'tier', v_tier,
    'remaining', v_limit - monthly_quota_used
  ) INTO v_result
  FROM public.profiles
  WHERE id = v_target_profile_id;

  RETURN v_result;
END;
$$;

-- 4. Stored Procedure: release_quota
-- Safely releases ONLY a matching 'reserved' ledger entry on analysis failure
CREATE OR REPLACE FUNCTION public.release_quota(p_user_id UUID, p_audit_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_res RECORD;
BEGIN
  -- Lock and find the specific reservation
  SELECT id, target_profile_id, tier, status
  INTO v_res
  FROM public.quota_reservations
  WHERE user_id = p_user_id AND audit_id = p_audit_id AND status = 'reserved'
  FOR UPDATE;

  IF NOT FOUND THEN
    -- Reservation already released or completed; do nothing
    RETURN;
  END IF;

  -- Mark reservation released
  UPDATE public.quota_reservations
  SET status = 'released'
  WHERE id = v_res.id;

  -- Safely decrement usage on target profile
  IF v_res.tier = 'free' THEN
    UPDATE public.profiles
    SET lifetime_free_audits_used = GREATEST(0, COALESCE(lifetime_free_audits_used, 1) - 1)
    WHERE id = v_res.target_profile_id;
  ELSE
    UPDATE public.profiles
    SET monthly_quota_used = GREATEST(0, COALESCE(monthly_quota_used, 1) - 1)
    WHERE id = v_res.target_profile_id;
  END IF;
END;
$$;

-- 5. Stored Procedure: commit_quota
-- Marks reservation 'completed' upon successful audit analysis persistence
CREATE OR REPLACE FUNCTION public.commit_quota(p_user_id UUID, p_audit_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  UPDATE public.quota_reservations
  SET status = 'completed'
  WHERE user_id = p_user_id AND audit_id = p_audit_id AND status = 'reserved';
END;
$$;

