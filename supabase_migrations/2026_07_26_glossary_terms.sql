-- Migration: glossary_terms — the personal term dictionary
-- Date: 2026-07-26
-- Author: "Ask about a term or phrase" revamp (home menu feature)
--
-- One row per saved term: the user asks for a plain-words explanation of a
-- medical term, can edit the AI's definition, and saves it to their library.
-- User-editable CRUD, so the RLS posture is owner FOR-ALL (accounts pattern),
-- unlike the append-only audit tables. The Flask backend uses the service
-- role (bypasses RLS); real ownership enforcement is the storage layer's
-- .eq('user_id', ...) filters — RLS is defense-in-depth.

CREATE TABLE IF NOT EXISTS glossary_terms (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  term        TEXT NOT NULL,
  definition  TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS glossary_terms_user_created_idx
  ON glossary_terms (user_id, created_at DESC);

ALTER TABLE glossary_terms ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS glossary_terms_own ON glossary_terms;
CREATE POLICY glossary_terms_own ON glossary_terms FOR ALL
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
