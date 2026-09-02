-- ==============================================================================
-- TRACECLAUSE AI v2 — SUPABASE DATABASE SCHEMA MIGRATION
-- Paste and execute this script inside your Supabase SQL Editor.
-- ==============================================================================

-- 1. Enable pgvector extension for dense RAG vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create User Profiles Table
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
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS on profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view and update own profile" ON public.profiles
  FOR ALL USING (auth.uid() = id);

-- 3. Create Workspaces Table (For Team Tier)
CREATE TABLE IF NOT EXISTS public.workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  seat_limit INT DEFAULT 4,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;

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

-- 4. Create Workspace Members Table
CREATE TABLE IF NOT EXISTS public.workspace_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('owner', 'member')) DEFAULT 'member',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, user_id)
);

ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;

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

-- 5. Create Contract Reports Table (Zero Raw File Storage — Metadata & Redlines Only)
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

-- Enable RLS on contract_reports
ALTER TABLE public.contract_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can access own or workspace reports" ON public.contract_reports
  FOR ALL USING (
    auth.uid() = user_id OR (
      workspace_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.workspace_members 
        WHERE workspace_id = public.contract_reports.workspace_id AND user_id = auth.uid()
      )
    )
  );

-- 6. Create Contract Embeddings Table (Dual Vector Embeddings for OpenAI & Gemini RAG)
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

-- Enable RLS on contract_embeddings
ALTER TABLE public.contract_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can access own or workspace vector embeddings" ON public.contract_embeddings
  FOR ALL USING (
    auth.uid() = user_id OR (
      workspace_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.workspace_members 
        WHERE workspace_id = public.contract_embeddings.workspace_id AND user_id = auth.uid()
      )
    )
  );

-- Create Index for Fast HNSW Vector Similarity Search
CREATE INDEX IF NOT EXISTS contract_embeddings_hnsw_idx 
  ON public.contract_embeddings 
  USING hnsw (embedding vector_cosine_ops);

