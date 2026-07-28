-- Migration: connection_map — concept vocabulary
-- Date: 2026-07-28
-- Author: Connection map Phase 1 (SPEC-connection-map.md §4.1, PLAN.md)
--
-- The controlled vocabulary every connection-map relationship is built from.
-- Extraction pass 1 may only emit concepts that exist here, so this table is
-- the boundary that keeps an LLM from inventing its own ontology at runtime.
--
-- Seeded from config/connection_map/concepts_breast.yaml by
-- scripts/seed_connection_map_concepts.py. The enum value lists below mirror
-- lib/connection_map/concepts.py, which is the Python source of truth;
-- tests/test_connection_map_migrations.py cross-checks the two.
--
-- Not patient data: no user_id, no RLS policy. RLS is enabled with NO policies
-- so anon/authenticated see nothing; the Flask backend reaches it through the
-- service role, which bypasses RLS by design (same posture the glossary and
-- accounts migrations document).
--
-- display_patient stays NULL until an attesting physician writes it during
-- review (§5.4 "Reword"); publication (§5.7) refuses any concept without one.

CREATE TABLE IF NOT EXISTS concept (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                TEXT NOT NULL UNIQUE,
  domain              TEXT NOT NULL CHECK (domain IN (
                        'biomarker','treatment','procedure',
                        'symptom','lab_or_measure','daily_life')),
  display_clinical    TEXT NOT NULL,
  display_patient     TEXT,              -- NULL until physician review; required to publish
  terminology_system  TEXT,
  terminology_code    TEXT,
  instrument          TEXT CHECK (instrument IN (
                        'lab','ehr_field','report_scan',
                        'pro_instrument','self_report_chat')),
  cancer_scopes       TEXT[] NOT NULL DEFAULT '{}',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Instantiation and extraction both filter by cancer scope, then by domain.
CREATE INDEX IF NOT EXISTS concept_cancer_scopes_idx ON concept USING GIN (cancer_scopes);
CREATE INDEX IF NOT EXISTS concept_domain_idx ON concept (domain);

ALTER TABLE concept ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE concept IS
  'Connection-map controlled vocabulary (SPEC §4.1). Seeded from config/connection_map/. '
  'display_patient is filled in by an attesting physician, never by the pipeline.';
