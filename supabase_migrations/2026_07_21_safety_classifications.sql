-- Migration: safety_classifications — audit log for the pre-chat safety classifier
-- Date: 2026-07-21
-- Author: Sage safety layer (supervisor mandate, sage-implementation-guidelines.html)
--
-- One row per NON-NONE classification of an inbound chat message. This is the
-- supervisor's "log every non-NONE classification with the message, tier, and
-- rationale" requirement, satisfied in the DATABASE (user-scoped, RLS, same
-- posture as messages/patient_events) rather than console logs, which carry
-- no PHI. Reviewed weekly via scripts/safety_report.py; rule_matched = false
-- rows are the AI-judgment calls that feed the next rules-file version.
--
-- Append-only by design: no UPDATE/DELETE policies. Deletion happens only via
-- delete_all_user_data (service role) for MHMDA/GDPR right-to-delete parity.

CREATE TABLE IF NOT EXISTS safety_classifications (
  id               BIGSERIAL PRIMARY KEY,
  user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  conversation_id  TEXT,
  message          TEXT NOT NULL,           -- sanitize_query'd inbound message
  tier             TEXT NOT NULL CHECK (tier IN ('T1','T2','T3','MH')),
  category         TEXT,
  confidence       REAL,
  rationale        TEXT,
  rule_matched     BOOLEAN NOT NULL DEFAULT FALSE,
  source           TEXT NOT NULL DEFAULT 'llm',   -- rules | llm | merged | rules-fallback
  rules_version    TEXT,
  model            TEXT,
  latency_ms       INTEGER,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS safety_class_user_time_idx
  ON safety_classifications (user_id, created_at DESC);
-- The weekly review scans rule_matched = false (AI-judgment calls) globally.
CREATE INDEX IF NOT EXISTS safety_class_review_idx
  ON safety_classifications (rule_matched, created_at DESC);

ALTER TABLE safety_classifications ENABLE ROW LEVEL SECURITY;

-- Users may read their own rows; all writes go through the service role
-- (same posture as patient_events).
DROP POLICY IF EXISTS safety_class_select ON safety_classifications;
CREATE POLICY safety_class_select ON safety_classifications
  FOR SELECT USING (user_id = auth.uid());
