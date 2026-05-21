-- Consent withdrawal log — MHMDA requires the affordance to withdraw consent
-- separately from deleting the account. Each toggle off is a row here.
--
-- DRAFT — apply via the Supabase SQL editor as part of the Task 4 rollout.

CREATE TABLE IF NOT EXISTS consent_withdrawals (
  id           BIGSERIAL PRIMARY KEY,
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  consent_key  TEXT NOT NULL,
    -- 'consent_collection' | 'consent_sharing' | 'consent_terms'
  action       TEXT NOT NULL DEFAULT 'withdraw',
    -- 'withdraw' | 'restore' — restore lets the user opt back in
  reason       TEXT,
    -- optional free-text the UI may collect ("changing my mind", etc.)
  consent_version TEXT,
  ip_hash      TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS consent_withdrawals_user_idx
  ON consent_withdrawals (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS consent_withdrawals_key_idx
  ON consent_withdrawals (user_id, consent_key, created_at DESC);

ALTER TABLE consent_withdrawals ADD CONSTRAINT consent_withdrawals_key_check
  CHECK (consent_key IN ('consent_collection','consent_sharing','consent_terms'));

ALTER TABLE consent_withdrawals ADD CONSTRAINT consent_withdrawals_action_check
  CHECK (action IN ('withdraw','restore'));

-- Row-level security: a user can only see / write their own rows.
ALTER TABLE consent_withdrawals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS consent_withdrawals_select ON consent_withdrawals;
CREATE POLICY consent_withdrawals_select ON consent_withdrawals
  FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS consent_withdrawals_insert ON consent_withdrawals;
CREATE POLICY consent_withdrawals_insert ON consent_withdrawals
  FOR INSERT WITH CHECK (user_id = auth.uid());

-- Service role bypasses RLS for the API endpoint to write on the user's behalf.
