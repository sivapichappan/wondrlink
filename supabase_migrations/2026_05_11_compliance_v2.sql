-- Migration: WondrChat MHMDA / compliance v2
-- Date: 2026-05-11
-- Author: compliance hardening sprint
--
-- Adds two columns to user_acknowledgements to support:
--   - consent_metadata (JSONB): full audit trail of which specific consents
--     a user accepted, when, from what state, age confirmation, etc.
--   - consent_version (TEXT): the version of the consent terms accepted.
--     Used to detect users who need re-consent when terms change.
--
-- Backwards-compatible: existing rows get '{}' and 'v1' defaults so the
-- migration is safe to apply with users already in the table. Code in
-- lib/compliance.py treats any version < CURRENT_CONSENT_VERSION as
-- requiring re-consent on next login.

ALTER TABLE user_acknowledgements
  ADD COLUMN IF NOT EXISTS consent_metadata JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS consent_version TEXT DEFAULT 'v1';

-- Index used by Phase 3 (existing-user migration) to identify users on
-- old consent versions efficiently.
CREATE INDEX IF NOT EXISTS idx_user_acks_consent_version
  ON user_acknowledgements (consent_version);

-- Sanity check column was added
COMMENT ON COLUMN user_acknowledgements.consent_metadata IS
  'MHMDA-compliant consent record: which consents accepted, state, age, timestamp.';
COMMENT ON COLUMN user_acknowledgements.consent_version IS
  'Version tag of the consent terms accepted. < CURRENT_CONSENT_VERSION forces re-consent.';
