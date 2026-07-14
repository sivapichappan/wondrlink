-- Migration: patient_events — the append-only patient timeline
-- Date: 2026-07-15
-- Author: patient lifecycle foundation (passive profile shift)
--
-- One row per thing that happened to / was learned about a patient:
--   belief_add | belief_update | belief_confirm | belief_invalidate | belief_reject |
--   pending_created | shadow_extraction | screening_score | visit_recap |
--   stage_transition | question_asked
--
-- The future connections-layer Modeler consumes this as the patient's
-- longitudinal record. Bi-temporal-lite: `occurred_at` is clinical time
-- (best-effort), `recorded_at` is system time.
--
-- Append-only by design: no UPDATE/DELETE policies. Deletion happens only via
-- delete_all_user_data (service role) for MHMDA/GDPR right-to-delete parity.

CREATE TABLE IF NOT EXISTS patient_events (
  id           BIGSERIAL PRIMARY KEY,
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  kind         TEXT NOT NULL,
  path         TEXT,
  payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
  source       TEXT NOT NULL DEFAULT 'system',
  session_id   TEXT,
  occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS patient_events_user_time_idx
  ON patient_events (user_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS patient_events_user_kind_idx
  ON patient_events (user_id, kind, recorded_at DESC);

ALTER TABLE patient_events ENABLE ROW LEVEL SECURITY;

-- Users may read their own timeline; all writes go through the service role
-- (same posture as consent_withdrawals).
DROP POLICY IF EXISTS patient_events_select ON patient_events;
CREATE POLICY patient_events_select ON patient_events
  FOR SELECT USING (user_id = auth.uid());

COMMENT ON TABLE patient_events IS
  'Append-only patient timeline for the passive-lifecycle model (beliefs, screenings, recaps, stage transitions).';
