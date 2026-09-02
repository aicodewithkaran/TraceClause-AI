-- ==============================================================================
-- TRACECLAUSE AI v2 — MIGRATION: TIER GATING & MULTI-SEAT WORKSPACES
-- ==============================================================================

-- 1. Refactor public.profiles Table
ALTER TABLE public.profiles 
  ADD COLUMN IF NOT EXISTS lifetime_free_audits_used INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS monthly_quota_used INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_quota_reset TIMESTAMPTZ DEFAULT NOW();

-- Update subscription_tier check constraint
ALTER TABLE public.profiles 
  DROP CONSTRAINT IF EXISTS profiles_subscription_tier_check;

ALTER TABLE public.profiles 
  ADD CONSTRAINT profiles_subscription_tier_check 
  CHECK (subscription_tier IN ('free', 'solo', 'team'));

-- 2. Create Workspaces Table (For Team Tier)
CREATE TABLE IF NOT EXISTS public.workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  seat_limit INT DEFAULT 4,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;

-- 3. Create Workspace Members Table
CREATE TABLE IF NOT EXISTS public.workspace_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('owner', 'member')) DEFAULT 'member',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, user_id)
);

ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;

-- 4. Associate Workspaces with Reports & Embeddings
ALTER TABLE public.contract_reports 
  ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL;

ALTER TABLE public.contract_embeddings 
  ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL;

-- 5. RLS Policies for Workspaces & Workspace Members
CREATE POLICY "Users can view workspaces they belong to" ON public.workspaces
  FOR SELECT USING (
    auth.uid() = owner_id OR 
    EXISTS (
      SELECT 1 FROM public.workspace_members 
      WHERE workspace_id = public.workspaces.id AND user_id = auth.uid()
    )
  );

CREATE POLICY "Owners can manage their workspaces" ON public.workspaces
  FOR ALL USING (auth.uid() = owner_id);

CREATE POLICY "Users can view workspace members for their workspaces" ON public.workspace_members
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.workspace_members wm 
      WHERE wm.workspace_id = public.workspace_members.workspace_id AND wm.user_id = auth.uid()
    )
  );

CREATE POLICY "Owners can manage workspace members" ON public.workspace_members
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.workspaces w 
      WHERE w.id = public.workspace_members.workspace_id AND w.owner_id = auth.uid()
    )
  );

-- Update RLS Policies for Contract Reports & Embeddings to support Workspaces
DROP POLICY IF EXISTS "Users can access own reports" ON public.contract_reports;
CREATE POLICY "Users can access own or workspace reports" ON public.contract_reports
  FOR ALL USING (
    auth.uid() = user_id OR (
      workspace_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.workspace_members 
        WHERE workspace_id = public.contract_reports.workspace_id AND user_id = auth.uid()
      )
    )
  );

DROP POLICY IF EXISTS "Users can access own vector embeddings" ON public.contract_embeddings;
CREATE POLICY "Users can access own or workspace vector embeddings" ON public.contract_embeddings
  FOR ALL USING (
    auth.uid() = user_id OR (
      workspace_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.workspace_members 
        WHERE workspace_id = public.contract_embeddings.workspace_id AND user_id = auth.uid()
      )
    )
  );
