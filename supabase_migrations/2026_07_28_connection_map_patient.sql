-- Migration: connection_map — patient edges + append-only event log
-- Date: 2026-07-28
-- Author: Connection map Phase 1 (SPEC-connection-map.md §4.6, §4.7, PLAN.md)
--
-- The per-patient half of the map. A relationship copies onto a patient only
-- when both endpoints are already CONFIRMED facts in the belief store (§7.1),
-- and only from a published version (acceptance #17) — the runtime that does
-- that arrives in Phase 7. Phase 1 creates the tables so the shape is settled
-- and the right-to-delete path exists from the first row onward.
--
-- These are patient-data tables, so unlike the master side they get the house
-- own-rows RLS posture (defense in depth; the backend still reaches them with
-- the service role) and both are wired into delete_all_user_data() in
-- lib/supabase_storage.py in this same change.
--
-- APPEND-ONLY, WITH A CARVE-OUT. patient_edge_event is append-only: a trigger
-- rejects UPDATE. DELETE is deliberately still allowed, because MHMDA/GDPR
-- right-to-delete has to be able to remove a patient's rows. That is the
-- opposite of the Phase 2 attestation and audit_log tables, which are not
-- patient data and therefore get hard append-only (acceptance #25).
--
-- No confidence value stored here is ever rendered to a patient (§3, §4.8):
-- alpha/beta are internal Beta-posterior counts.

CREATE TABLE IF NOT EXISTS patient_edge (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  master_edge_id  UUID NOT NULL REFERENCES master_edge(id) ON DELETE RESTRICT,
  map_version_id  UUID NOT NULL REFERENCES master_map_version(id) ON DELETE RESTRICT,
  status          TEXT NOT NULL DEFAULT 'instantiated' CHECK (status IN (
                    'instantiated','proposed','confirmed','refuted','retired')),
  -- Copied from the master edge's priors at instantiation, then updated by
  -- patient answers. Integers only (§4.8).
  alpha           INT NOT NULL CHECK (alpha > 0),
  beta            INT NOT NULL CHECK (beta > 0),
  last_asked_at   TIMESTAMPTZ,
  ask_count       INT NOT NULL DEFAULT 0 CHECK (ask_count >= 0),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT patient_edge_patient_master_key UNIQUE (patient_id, master_edge_id)
);

CREATE INDEX IF NOT EXISTS patient_edge_patient_status_idx ON patient_edge (patient_id, status);

CREATE TABLE IF NOT EXISTS patient_edge_event (
  id                   BIGSERIAL PRIMARY KEY,
  patient_edge_id      UUID NOT NULL REFERENCES patient_edge(id) ON DELETE CASCADE,
  -- Denormalized owner. Not in §4.6, added so right-to-delete can delete by
  -- user id in one PostgREST call and so the RLS policy needs no join.
  patient_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  event_type           TEXT NOT NULL,
  from_status          TEXT CHECK (from_status IS NULL OR from_status IN (
                         'instantiated','proposed','confirmed','refuted','retired')),
  to_status            TEXT CHECK (to_status IS NULL OR to_status IN (
                         'instantiated','proposed','confirmed','refuted','retired')),
  -- Phase 7 owns question instances; the FK lands with them.
  question_instance_id UUID,
  actor                TEXT NOT NULL,
  payload              JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS patient_edge_event_edge_time_idx
  ON patient_edge_event (patient_edge_id, created_at DESC);
CREATE INDEX IF NOT EXISTS patient_edge_event_patient_idx
  ON patient_edge_event (patient_id);

-- Append-only: reject UPDATE, allow DELETE (right-to-delete carve-out above).
CREATE OR REPLACE FUNCTION connection_map_block_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'connection_map: % is append-only', TG_TABLE_NAME;
END;
$$;

DROP TRIGGER IF EXISTS patient_edge_event_append_only ON patient_edge_event;
CREATE TRIGGER patient_edge_event_append_only
  BEFORE UPDATE ON patient_edge_event
  FOR EACH ROW EXECUTE FUNCTION connection_map_block_update();

ALTER TABLE patient_edge ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_edge_event ENABLE ROW LEVEL SECURITY;

-- Users may read their own rows; all writes go through the service role
-- (same posture as patient_events and safety_classifications).
DROP POLICY IF EXISTS patient_edge_select ON patient_edge;
CREATE POLICY patient_edge_select ON patient_edge
  FOR SELECT USING (patient_id = auth.uid());

DROP POLICY IF EXISTS patient_edge_event_select ON patient_edge_event;
CREATE POLICY patient_edge_event_select ON patient_edge_event
  FOR SELECT USING (patient_id = auth.uid());

COMMENT ON TABLE patient_edge IS
  'Per-patient instantiation of published master edges (SPEC §4.6). alpha/beta are '
  'internal Beta counts and are never rendered to a patient.';
COMMENT ON TABLE patient_edge_event IS
  'Append-only transition log (SPEC §4.6). UPDATE is blocked by trigger; DELETE stays '
  'open for MHMDA/GDPR right-to-delete via delete_all_user_data().';
