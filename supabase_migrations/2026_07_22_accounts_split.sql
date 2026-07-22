-- Migration: accounts — the literal account/patient split
-- Date: 2026-07-22
-- Author: Sage implementation-guidelines adoption (Workstream I)
--
-- The guidelines specify an `accounts` table (keyed to auth.uid, owned by
-- the phone number) separate from patient_profiles, because the account
-- holder may be a caregiver. The three account-level columns added to
-- patient_profiles by 2026_07_18_sage_account_fields.sql move here.
--
-- patient_profiles stays keyed by user_id (same VALUE as accounts.id —
-- renaming the key column would ripple through ~17 call sites for zero
-- behavior change; see docs/sage-implementation-guidelines-notes.md #7).
--
-- The old patient_profiles columns are RETAINED for one release as the
-- rollback path; a follow-up migration drops perspective / relationship /
-- account_holder_name + the perspective CHECK once the new read path has
-- soaked.

CREATE TABLE IF NOT EXISTS accounts (
  id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  holder_name   TEXT,
  perspective   TEXT NOT NULL DEFAULT 'self'
                CHECK (perspective IN ('self', 'caregiver')),
  relationship  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;

-- Guidelines baseline policy: a row is visible and writable only by its
-- owner. (The Flask backend uses the service role, which bypasses RLS —
-- this is the database-level defense-in-depth posture the doc mandates.)
DROP POLICY IF EXISTS accounts_own ON accounts;
CREATE POLICY accounts_own ON accounts FOR ALL
  USING (id = auth.uid()) WITH CHECK (id = auth.uid());

-- Backfill from the 2026_07_18 columns (idempotent).
INSERT INTO accounts (id, holder_name, perspective, relationship)
SELECT user_id, account_holder_name, COALESCE(perspective, 'self'), relationship
FROM patient_profiles
ON CONFLICT (id) DO NOTHING;
