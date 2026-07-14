-- Migration: DORMANT model-improvement consent + pattern sink
-- Date: 2026-07-15
-- Author: patient lifecycle foundation (Phase 5 — built dormant)
--
-- STATUS: DRAFT / DORMANT. Nothing reads or writes these until
-- FEATURE_MODEL_IMPROVEMENT=true, which is gated on:
--   1. attorney review of the consent copy (new processing purpose:
--      "use de-identified patterns to improve WondrChat"),
--   2. a CURRENT_CONSENT_VERSION bump in lib/compliance.py,
--   3. the opt-in UI shipping.
-- See docs/compliance/model_improvement_dormant.md for the activation
-- checklist. Applying this migration changes NO runtime behavior.

-- Widen the consent-key CHECK to admit the future opt-IN key, and the action
-- CHECK to admit 'grant' (first-time opt-in — unlike the signup keys, this
-- key has no baseline so 'restore' alone can't express the first grant).
ALTER TABLE consent_withdrawals DROP CONSTRAINT IF EXISTS consent_withdrawals_consent_key_check;
ALTER TABLE consent_withdrawals ADD CONSTRAINT consent_withdrawals_consent_key_check
  CHECK (consent_key IN
    ('consent_collection','consent_sharing','consent_terms','consent_model_improvement'));

ALTER TABLE consent_withdrawals DROP CONSTRAINT IF EXISTS consent_withdrawals_action_check;
ALTER TABLE consent_withdrawals ADD CONSTRAINT consent_withdrawals_action_check
  CHECK (action IN ('withdraw','restore','grant'));

-- De-identified pattern sink. BY DESIGN this table has NO user_id column —
-- records are cohort-keyed only (cancer_slug|stage_group|topic bucket) and
-- must pass the PII leak guard before insert. k-anonymity (k>=20) is enforced
-- at any export/read: a pattern may only influence anything once >=20
-- distinct contributions exist for its cohort_key.
CREATE TABLE IF NOT EXISTS pattern_records (
  id          BIGSERIAL PRIMARY KEY,
  cohort_key  TEXT NOT NULL,
  record      JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS pattern_records_cohort_idx ON pattern_records (cohort_key, created_at DESC);

ALTER TABLE pattern_records ENABLE ROW LEVEL SECURITY;
-- Service-role only: no user-facing policies at all.

COMMENT ON TABLE pattern_records IS
  'DORMANT: de-identified cohort-keyed patterns for system improvement. No user_id by design. Activation gated on attorney review + consent-version bump (FEATURE_MODEL_IMPROVEMENT).';
