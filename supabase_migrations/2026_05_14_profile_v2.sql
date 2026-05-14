-- Phase 1 of the multi-cancer expansion — profile schema v2.
--
-- Adds universal core fields next to the existing patient_profiles row
-- (preserving raw_profile JSONB for dual-write/read during Phase 1):
--   - cancer_slug          canonical slug ('colorectal', 'breast', ...)
--   - role                 'patient' | 'caregiver'
--   - stage_group          normalized 0/I/II/III/IV/unknown
--   - treatment_intent     curative | palliative | unknown
--   - clinical             per-cancer JSONB validated against the
--                          config/cancers/<slug>/clinical.schema.json
--                          at write time by lib/profile_validator.py
--   - schema_version       'v2' (older rows stay NULL until migrated)
--
-- raw_profile and the existing denormalized columns are left in place —
-- they remain the read source of truth throughout Phase 1. After
-- scripts/migrate_profiles_v2.py has backfilled every row and the
-- read-path code is switched in Phase 2, the legacy columns can be
-- dropped in a follow-up migration.

ALTER TABLE patient_profiles
  ADD COLUMN IF NOT EXISTS cancer_slug TEXT,
  ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'patient',
  ADD COLUMN IF NOT EXISTS stage_group TEXT,
  ADD COLUMN IF NOT EXISTS treatment_intent TEXT,
  ADD COLUMN IF NOT EXISTS clinical JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS schema_version TEXT;

CREATE INDEX IF NOT EXISTS patient_profiles_cancer_slug_idx
  ON patient_profiles (cancer_slug);

-- Role + stage_group sanity constraints. Permissive enums because we
-- want write-side validation in Python (jsonschema-style errors)
-- rather than opaque DB constraint failures.
ALTER TABLE patient_profiles
  ADD CONSTRAINT patient_profiles_role_chk
  CHECK (role IS NULL OR role IN ('patient', 'caregiver'));

ALTER TABLE patient_profiles
  ADD CONSTRAINT patient_profiles_stage_group_chk
  CHECK (
    stage_group IS NULL
    OR stage_group IN ('0', 'I', 'II', 'III', 'IV', 'unknown')
  );

ALTER TABLE patient_profiles
  ADD CONSTRAINT patient_profiles_treatment_intent_chk
  CHECK (
    treatment_intent IS NULL
    OR treatment_intent IN ('curative', 'palliative', 'unknown')
  );
