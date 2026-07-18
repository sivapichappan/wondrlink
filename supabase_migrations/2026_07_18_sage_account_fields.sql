-- Migration: Sage account/patient split — account-level fields
-- Date: 2026-07-18
-- Author: Sage transition, Workstream B (see SAGE_TODO.md)
--
-- The account holder and the patient may be different people (caregiver mode).
-- Today they share one row; these columns record who is holding the account so
-- the caregiver voice layer (Workstream F) is a render-time change later.
-- Patient-side fields (name, birth year, gender, location) stay in raw_profile.
-- Runtime tolerates these columns being absent (column-missing fallback).

ALTER TABLE patient_profiles
  ADD COLUMN IF NOT EXISTS perspective TEXT NOT NULL DEFAULT 'self';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'patient_profiles_perspective_check'
  ) THEN
    ALTER TABLE patient_profiles ADD CONSTRAINT patient_profiles_perspective_check
      CHECK (perspective IN ('self', 'caregiver'));
  END IF;
END $$;

ALTER TABLE patient_profiles
  ADD COLUMN IF NOT EXISTS relationship TEXT;

ALTER TABLE patient_profiles
  ADD COLUMN IF NOT EXISTS account_holder_name TEXT;

COMMENT ON COLUMN patient_profiles.perspective IS
  'self = account holder is the patient; caregiver = account holder cares for the patient (Sage voice layer).';
