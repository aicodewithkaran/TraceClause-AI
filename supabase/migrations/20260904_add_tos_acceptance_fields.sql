-- ==============================================================================
-- TRACECLAUSE AI v2 — MIGRATION: TERMS OF SERVICE & PRIVACY POLICY ACCEPTANCE
-- ==============================================================================

-- Add tos_accepted_at and tos_accepted_version columns to public.profiles
ALTER TABLE public.profiles 
  ADD COLUMN IF NOT EXISTS tos_accepted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS tos_accepted_version TEXT;

-- Create an index on tos_accepted_version for fast lookups
CREATE INDEX IF NOT EXISTS idx_profiles_tos_accepted_version 
  ON public.profiles(tos_accepted_version);
