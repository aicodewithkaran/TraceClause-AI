-- ==============================================================================
-- TRACECLAUSE AI v2 — SUPABASE MASTER DATABASE SCHEMA
-- Paste and execute this entire script inside your Supabase SQL Editor.
-- Completely idempotent: can be safely executed repeatedly.
-- ==============================================================================

-- 1. Enable pgvector extension for dense RAG vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ==============================================================================
-- 2. CREATE ALL TABLES (Order-safe without circular dependencies)
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
  tos_accepted_at TIMESTAMPTZ,
  tos_accepted_version TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.2 Workspaces Table (For Team Tier Multi-Seat Collaboration)
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

-- 2.4 Contract Reports Table (In-Memory File Parsing — User-Controlled Audit Vault)
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

-- 2.5 Contract Embeddings Table (Dual Vector Embeddings for OpenAI & Gemini RAG)
CREATE TABLE IF NOT EXISTS public.contract_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID NOT NULL REFERENCES public.contract_reports(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL,
  clause_number INT NOT NULL,
  clause_text TEXT NOT NULL,
  embedding vector(1536), -- Supports OpenAI & Gemini native 1536-dim vectors
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.6 Quota Reservations Ledger Table (Atomic Check-and-Increment Engine)
CREATE TABLE IF NOT EXISTS public.quota_reservations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  target_profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  audit_id UUID NOT NULL,
  tier TEXT NOT NULL,
  status TEXT CHECK (status IN ('reserved', 'completed', 'released')) DEFAULT 'reserved',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.7 Processed Webhooks Table for Idempotent Razorpay Webhook Processing
CREATE TABLE IF NOT EXISTS public.processed_webhooks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE NOT NULL,
  event_type TEXT NOT NULL,
  provider TEXT DEFAULT 'razorpay',
  payload JSONB,
  processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 3. CREATE PERFORMANCE & SEARCH INDEXES
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_profiles_tos_accepted_version 
  ON public.profiles(tos_accepted_version);

CREATE INDEX IF NOT EXISTS contract_embeddings_hnsw_idx 
  ON public.contract_embeddings 
  USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_quota_reservations_user_audit 
  ON public.quota_reservations(user_id, audit_id);

CREATE INDEX IF NOT EXISTS idx_quota_reservations_status 
  ON public.quota_reservations(status);

CREATE INDEX IF NOT EXISTS idx_processed_webhooks_event_id 
  ON public.processed_webhooks(event_id);

-- ==============================================================================
-- 4. ENABLE ROW LEVEL SECURITY (RLS) ON ALL TABLES
-- ==============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contract_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contract_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quota_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processed_webhooks ENABLE ROW LEVEL SECURITY;

-- ==============================================================================
-- 5. ROW LEVEL SECURITY POLICIES (Idempotent Drop + Create)
-- ==============================================================================

-- 5.1 Profiles Policies
DROP POLICY IF EXISTS "Users can insert own profile" ON public.profiles;
CREATE POLICY "Users can insert own profile" ON public.profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "Users can view and update own profile" ON public.profiles;
CREATE POLICY "Users can view and update own profile" ON public.profiles
  FOR ALL USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

-- 5.2 Workspaces Policies (Now workspace_members table is guaranteed to exist)
DROP POLICY IF EXISTS "Users can view workspaces they belong to" ON public.workspaces;
CREATE POLICY "Users can view workspaces they belong to" ON public.workspaces
  FOR SELECT USING (
    auth.uid() = owner_id OR 
    EXISTS (
      SELECT 1 FROM public.workspace_members 
      WHERE workspace_id = public.workspaces.id AND user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Owners can manage their workspaces" ON public.workspaces;
CREATE POLICY "Owners can manage their workspaces" ON public.workspaces
  FOR ALL USING (auth.uid() = owner_id);

-- 5.3 Workspace Members Policies
DROP POLICY IF EXISTS "Users can view workspace members for their workspaces" ON public.workspace_members;
CREATE POLICY "Users can view workspace members for their workspaces" ON public.workspace_members
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.workspace_members wm 
      WHERE wm.workspace_id = public.workspace_members.workspace_id AND wm.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Owners can manage workspace members" ON public.workspace_members;
CREATE POLICY "Owners can manage workspace members" ON public.workspace_members
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.workspaces w 
      WHERE w.id = public.workspace_members.workspace_id AND w.owner_id = auth.uid()
    )
  );

-- 5.4 Contract Reports Policies
DROP POLICY IF EXISTS "Users can access own or workspace reports" ON public.contract_reports;
CREATE POLICY "Users can access own or workspace reports" ON public.contract_reports
  FOR ALL USING (
    auth.uid() = user_id OR (
      workspace_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.workspace_members 
        WHERE workspace_id = public.contract_reports.workspace_id AND user_id = auth.uid()
      )
    )
  );

-- 5.5 Contract Embeddings Policies
DROP POLICY IF EXISTS "Users can access own or workspace vector embeddings" ON public.contract_embeddings;
CREATE POLICY "Users can access own or workspace vector embeddings" ON public.contract_embeddings
  FOR ALL USING (
    auth.uid() = user_id OR (
      workspace_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.workspace_members 
        WHERE workspace_id = public.contract_embeddings.workspace_id AND user_id = auth.uid()
      )
    )
  );

-- 5.6 Quota Reservations Policies
DROP POLICY IF EXISTS "Users can view own quota reservations" ON public.quota_reservations;
CREATE POLICY "Users can view own quota reservations" ON public.quota_reservations
  FOR SELECT USING (auth.uid() = user_id);

-- ==============================================================================
-- 6. STORED PROCEDURES: reserve_quota, release_quota, commit_quota
-- ==============================================================================

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

  UPDATE public.quota_reservations
  SET status = 'released'
  WHERE id = v_res.id;

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

-- ==============================================================================
-- 7. AUTOMATIC PROFILE CREATION TRIGGER ON AUTH SIGNUP
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
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
