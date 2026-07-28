-- Migration: connection_map — published map versions
-- Date: 2026-07-28
-- Author: Connection map Phase 1 (SPEC-connection-map.md §4.5, §5.7, PLAN.md)
--
-- A published version is the unit a patient map is instantiated from: no
-- patient_edge may reference a relationship outside a published version
-- (acceptance #17). Publication itself is Phase 3 — this table exists now so
-- patient_edge can reference it and so the shape is settled before the gate is
-- written.
--
-- published_by is a bare UUID for now; Phase 2 introduces the reviewer table
-- and adds the foreign key. Deliberately not a reference to auth.users: a
-- reviewer is not a patient account (§5.1).
--
-- IMMUTABILITY (§4.5 "Published versions are immutable") is enforced by the
-- interim CHECK below plus a Phase 3 trigger. The trigger waits because the
-- publication gate owns the exact carve-outs (draft to published, superseding
-- a prior version), and writing it now would mean re-cutting it then.
--
-- Not patient data: RLS enabled, no policies (service role reaches it).

CREATE TABLE IF NOT EXISTS master_map_version (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cancer           TEXT NOT NULL,
  version          INT NOT NULL CHECK (version >= 1),
  status           TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft','published','superseded')),
  published_at     TIMESTAMPTZ,
  published_by     UUID,             -- Phase 2: REFERENCES reviewer(id)
  edge_ids         UUID[] NOT NULL DEFAULT '{}',
  frozen_hash      TEXT,
  governance_note  TEXT,             -- §5.7 requires non-null to publish
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- A published row must carry its publication stamp and content freeze.
  -- §5.7's full itemized gate (attestations, evidence re-verification,
  -- display_patient, patient_phrasing, governance_note) lands in Phase 3.
  CONSTRAINT master_map_version_published_fields_check
    CHECK (status <> 'published'
           OR (published_at IS NOT NULL
               AND frozen_hash IS NOT NULL
               AND governance_note IS NOT NULL)),
  CONSTRAINT master_map_version_cancer_version_key UNIQUE (cancer, version)
);

CREATE INDEX IF NOT EXISTS master_map_version_cancer_status_idx
  ON master_map_version (cancer, status);

ALTER TABLE master_map_version ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE master_map_version IS
  'Versioned publication unit for the connection map (SPEC §4.5). Published rows are '
  'immutable; the full publication gate and its trigger land with Phase 3.';
