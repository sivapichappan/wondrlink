-- Migration: patient_profiles.lifecycle_stage
-- Date: 2026-07-15
-- Author: patient lifecycle foundation (passive profile shift)
--
-- The patient's position in the passive lifecycle. A real column (not JSONB)
-- because it's read on every mobile render (drawer + My Care cue) and the
-- future Modeler will query cohorts by stage server-side. Follows the v2
-- column pattern from 2026_05_14_profile_v2.sql; save_profile's
-- column-missing fallback covers the pre-apply window.
--
-- Stages (monotonic — the app never auto-regresses a patient):
--   getting_to_know_you     default; learning the basics conversationally
--   understanding_treatment site known + (stage OR an active treatment)
--   connected               coverage >= 0.6 + biomarker + treatments known
--   trial_ready             trial-critical fields present (zip + stage) + 2 helpful

ALTER TABLE patient_profiles
  ADD COLUMN IF NOT EXISTS lifecycle_stage TEXT NOT NULL DEFAULT 'getting_to_know_you';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'lifecycle_stage_check'
  ) THEN
    ALTER TABLE patient_profiles ADD CONSTRAINT lifecycle_stage_check
      CHECK (lifecycle_stage IN
        ('getting_to_know_you','understanding_treatment','connected','trial_ready'));
  END IF;
END $$;

COMMENT ON COLUMN patient_profiles.lifecycle_stage IS
  'Passive-lifecycle stage; advanced monotonically by lib/question_policy.py coverage rules.';
