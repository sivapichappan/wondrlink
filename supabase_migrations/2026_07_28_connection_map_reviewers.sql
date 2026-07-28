-- Migration: connection_map — reviewer identity, scoping, audit log
-- Date: 2026-07-28
-- Author: Connection map Phase 2 (SPEC-connection-map.md §5.1-§5.3, §5.9)
--
-- Who may review, what they may review, and an immutable record of everything
-- they did. The restricted database account that keeps reviewers away from
-- patient data lives in the companion migration
-- 2026_07_28_connection_map_sage_review_role.sql, which must be applied AFTER
-- this one (it grants on these tables).
--
-- A reviewer is NOT a patient account. Reviewers authenticate as their own
-- auth.users row and never hold a patient profile; §5.1 requires that
-- exclusivity to be enforced by the database, which the triggers below do in
-- both directions.
--
-- audit_log is HARD append-only: UPDATE and DELETE both raise (acceptance #25).
-- That is stricter than patient_edge_event, which must still allow DELETE for
-- right-to-delete. The difference is deliberate: audit_log holds no patient
-- data, so nothing in it is a patient's to erase.

-- ---------------------------------------------------------------------------
-- reviewer
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reviewer (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_user_id   UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
  email          TEXT NOT NULL UNIQUE,
  full_name      TEXT NOT NULL,
  credential     TEXT NOT NULL CHECK (credential IN (
                   'MD','DO','NP','PA','PharmD','RN','other')),
  npi            TEXT,
  license_state  TEXT,
  specialty      TEXT,
  institution    TEXT,
  affiliation    TEXT NOT NULL CHECK (affiliation IN ('internal','external')),
  role           TEXT NOT NULL CHECK (role IN (
                   'observer','reviewer_clinical','reviewer_attesting','admin')),
  status         TEXT NOT NULL DEFAULT 'invited'
                   CHECK (status IN ('invited','active','revoked')),
  invited_by     UUID REFERENCES reviewer(id),
  activated_at   TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- §5.1: only a physician may attest. Enforced here rather than in the
  -- application because it is the premise the whole attestation record rests on.
  CONSTRAINT reviewer_attesting_is_physician_check
    CHECK (role <> 'reviewer_attesting' OR credential IN ('MD','DO')),
  -- An active reviewer has actually completed activation (§5.2 step 3).
  CONSTRAINT reviewer_active_has_timestamp_check
    CHECK (status <> 'active' OR activated_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS reviewer_status_idx ON reviewer (status);
CREATE INDEX IF NOT EXISTS reviewer_auth_user_idx ON reviewer (auth_user_id);

-- ---------------------------------------------------------------------------
-- reviewer_assignment — §5.3 scoping. For v1 every assignment is breast.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reviewer_assignment (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reviewer_id  UUID NOT NULL REFERENCES reviewer(id) ON DELETE CASCADE,
  cancer       TEXT NOT NULL,
  -- Tier C is included ahead of its activation (owner decision D2, PLAN.md);
  -- an assignment naming a tier no edge can yet carry is harmless.
  tiers        TEXT[] NOT NULL DEFAULT ARRAY['A','B'],
  granted_by   UUID REFERENCES reviewer(id),
  granted_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at   TIMESTAMPTZ,
  -- cardinality(), NOT array_length(): array_length of an empty array is NULL,
  -- NULL >= 1 is NULL, and a CHECK passes on NULL. The obvious spelling would
  -- have silently admitted an assignment granting review rights over no tiers
  -- at all. cardinality() returns 0.
  CONSTRAINT reviewer_assignment_tiers_check
    CHECK (tiers <@ ARRAY['A','B','C']::TEXT[] AND cardinality(tiers) > 0)
);

-- Idempotent re-add, per the repo rule on changing a CHECK: drop every
-- historical name first. This constraint shipped once with array_length().
ALTER TABLE reviewer_assignment
  DROP CONSTRAINT IF EXISTS reviewer_assignment_tiers_check;
ALTER TABLE reviewer_assignment
  ADD CONSTRAINT reviewer_assignment_tiers_check
  CHECK (tiers <@ ARRAY['A','B','C']::TEXT[] AND cardinality(tiers) > 0);

CREATE INDEX IF NOT EXISTS reviewer_assignment_reviewer_idx
  ON reviewer_assignment (reviewer_id, cancer);

-- ---------------------------------------------------------------------------
-- audit_log — §5.9. Every reviewer action, invitation, role change,
-- assignment change, and publication writes a row.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
  id            BIGSERIAL PRIMARY KEY,
  actor_id      UUID,                  -- reviewer.id; null for system actions
  actor_role    TEXT,
  action        TEXT NOT NULL,
  target_table  TEXT,
  target_id     TEXT,
  before_hash   TEXT,
  after_hash    TEXT,
  metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_log_actor_time_idx ON audit_log (actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_target_idx ON audit_log (target_table, target_id);

-- Hard append-only: both UPDATE and DELETE raise (acceptance #25). No
-- right-to-delete carve-out here, unlike patient_edge_event: audit_log holds
-- no patient data.
CREATE OR REPLACE FUNCTION connection_map_block_write()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  RAISE EXCEPTION 'connection_map: % is append-only (% rejected)', TG_TABLE_NAME, TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log;
CREATE TRIGGER audit_log_append_only
  BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION connection_map_block_write();

-- ---------------------------------------------------------------------------
-- §5.1 / acceptance #5 — a reviewer account and a patient account are
-- mutually exclusive, enforced in the database, in both directions.
--
-- Direction 1 (here): a reviewer row cannot point at an auth user who already
-- has a patient profile. Direction 2 (below) blocks the reverse and therefore
-- has to attach to patient_profiles, an existing table. It is guarded on that
-- table existing, because sage-dev has not been through its bring-up yet.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_reviewer_not_a_patient()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  v_is_patient BOOLEAN;
BEGIN
  IF NEW.auth_user_id IS NULL THEN
    RETURN NEW;
  END IF;

  IF to_regclass('public.patient_profiles') IS NULL THEN
    RETURN NEW;
  END IF;

  -- Dynamic EXECUTE, not a plain EXISTS. PL/pgSQL prepares a static SQL
  -- expression as one statement and parse analysis resolves every relation in
  -- it BEFORE any of it runs, so a static reference to patient_profiles fails
  -- with "relation does not exist" on an environment that has not been through
  -- bring-up, even though the to_regclass guard above was meant to skip it.
  -- Deferring the reference to run time is what makes the guard real.
  EXECUTE 'SELECT EXISTS (SELECT 1 FROM patient_profiles WHERE user_id = $1)'
     INTO v_is_patient
    USING NEW.auth_user_id;

  IF v_is_patient THEN
    RAISE EXCEPTION
      'connection_map: this account already holds a patient profile; a clinician who is also a patient needs a second account';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS reviewer_not_a_patient ON reviewer;
CREATE TRIGGER reviewer_not_a_patient
  BEFORE INSERT OR UPDATE OF auth_user_id ON reviewer
  FOR EACH ROW EXECUTE FUNCTION connection_map_reviewer_not_a_patient();

CREATE OR REPLACE FUNCTION connection_map_patient_not_a_reviewer()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM reviewer r WHERE r.auth_user_id = NEW.user_id) THEN
    RAISE EXCEPTION
      'connection_map: this account is a reviewer account and cannot hold a patient profile';
  END IF;
  RETURN NEW;
END;
$$;

-- patient_profiles is an existing patient table and does not exist on an
-- unseeded dev project, so attach conditionally. Re-run this migration after
-- sage-dev bring-up to install the guard there.
DO $$
BEGIN
  IF to_regclass('public.patient_profiles') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS patient_not_a_reviewer ON patient_profiles';
    EXECUTE 'CREATE TRIGGER patient_not_a_reviewer '
            'BEFORE INSERT OR UPDATE OF user_id ON patient_profiles '
            'FOR EACH ROW EXECUTE FUNCTION connection_map_patient_not_a_reviewer()';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- RLS. These tables are reached by the service role (which bypasses RLS) and
-- by sage_review (which does NOT — see the companion migration for its
-- policies). Enabled here with no policies so anon/authenticated see nothing.
-- ---------------------------------------------------------------------------
ALTER TABLE reviewer ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviewer_assignment ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE reviewer IS
  'Physician and staff reviewer identities (SPEC 5.1). Mutually exclusive with patient accounts, enforced by trigger in both directions.';
COMMENT ON TABLE reviewer_assignment IS
  'Which cancers and tiers a reviewer may work on (SPEC 5.3).';
COMMENT ON TABLE audit_log IS
  'Append-only record of reviewer actions (SPEC 5.9). UPDATE and DELETE both raise; no patient data, so no right-to-delete carve-out.';
