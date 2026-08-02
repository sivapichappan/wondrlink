-- Migration: reviewers apply for access, and get a sandbox to test in
-- Date: 2026-08-05
-- Author: Reviewer-in-app wave 1 (SPEC-connection-map.md §5.2, §5.5)
--
-- WHY. A reviewer is currently a walled garden: the app sends them to the review
-- queue and refuses to let them leave, so a physician vouching for patient-facing
-- content has never seen the product it appears in. And reviewer accounts are
-- created by a script on a laptop, so a clinician has no way to ask for access.
--
-- Owner direction: an "oncologist reviewer" option at sign-up, credentials
-- collected, an admin approvals dashboard, then the NORMAL app with Approvals as
-- one item in the sidebar.
--
-- §5.2 says "No self-registration. No public signup." That intent is kept: anyone
-- may APPLY, nobody may SIGN until an admin activates them. A pending applicant
-- gets 403 from every review route exactly as a stranger does.
--
-- THE CONSTRAINT THAT SHAPES ALL OF THIS. A reviewer may not hold a patient
-- profile — enforced by triggers in both directions since 2026_07_28 and verified
-- against production. So a reviewer's chat does NOT get a patient profile. It gets
-- a synthetic patient in its own tables (§5.5), and the exclusion is left exactly
-- as it is.

-- ---------------------------------------------------------------------------
-- 1. A reviewer can now have ASKED, which is different from having been invited.
--
--    'invited'   an admin created the row and is waiting for them to activate
--    'requested' THEY applied and are waiting for an admin
--
--    An approvals dashboard has to tell those apart: one is a reminder to chase,
--    the other is a decision to make. Both are equally not-active, so every
--    existing status check keeps working untouched — is_active_reviewer and the
--    review blueprint's before_request both test for 'active' exactly.
-- ---------------------------------------------------------------------------
ALTER TABLE reviewer DROP CONSTRAINT IF EXISTS reviewer_status_check;
ALTER TABLE reviewer
  ADD CONSTRAINT reviewer_status_check
  CHECK (status IN ('requested', 'invited', 'active', 'revoked'));

-- Why they were turned down, when they were. Free text, admin-authored.
ALTER TABLE reviewer ADD COLUMN IF NOT EXISTS decision_note TEXT;
ALTER TABLE reviewer ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;
ALTER TABLE reviewer ADD COLUMN IF NOT EXISTS decided_by UUID REFERENCES reviewer(id);

COMMENT ON COLUMN reviewer.status IS
  'requested = they applied and an admin must decide; invited = an admin created the row and they must activate; active = may work; revoked = may not. Only active passes any review route.';

-- ---------------------------------------------------------------------------
-- 2. The synthetic patient a reviewer's chat runs on (§5.5).
--
--    One per reviewer, so two physicians testing at the same time never land in
--    each other's conversation and one's experiments never change what the next
--    one sees.
--
--    is_synthetic is redundant in a table that holds nothing else — and it is here
--    anyway, because §5.5's test is written as "a reviewer session cannot open a
--    chat bound to any patient_id where is_synthetic = false", and a test that
--    cannot be written the way the spec states it tends not to get written.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sandbox_patient (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reviewer_id   UUID NOT NULL UNIQUE REFERENCES reviewer(id) ON DELETE CASCADE,
  is_synthetic  BOOLEAN NOT NULL DEFAULT TRUE,
  raw_profile   JSONB NOT NULL DEFAULT '{}'::jsonb,
  cancer_slug   TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- Not a default that can be overridden: a row in this table IS synthetic, and
  -- nothing may ever write a real patient here.
  CONSTRAINT sandbox_patient_is_always_synthetic CHECK (is_synthetic)
);

CREATE INDEX IF NOT EXISTS sandbox_patient_reviewer_idx ON sandbox_patient (reviewer_id);

-- Separate tables rather than a flag on conversations/messages. A flag relies on
-- every analytics, modeler and export query remembering to filter it out; a
-- separate table cannot be picked up by forgetting.
CREATE TABLE IF NOT EXISTS sandbox_conversation (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sandbox_patient_id  UUID NOT NULL REFERENCES sandbox_patient(id) ON DELETE CASCADE,
  title               TEXT,
  map_version_id      UUID REFERENCES master_map_version(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sandbox_conversation_patient_idx
  ON sandbox_conversation (sandbox_patient_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS sandbox_message (
  id               BIGSERIAL PRIMARY KEY,
  conversation_id  UUID NOT NULL REFERENCES sandbox_conversation(id) ON DELETE CASCADE,
  role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content          TEXT NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sandbox_message_conversation_idx
  ON sandbox_message (conversation_id, created_at);

ALTER TABLE sandbox_patient ENABLE ROW LEVEL SECURITY;
ALTER TABLE sandbox_conversation ENABLE ROW LEVEL SECURITY;
ALTER TABLE sandbox_message ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE sandbox_patient IS
  'Synthetic patient backing a reviewer test chat (SPEC §5.5). One per reviewer. Never a real person; a reviewer still cannot hold a patient_profiles row.';
COMMENT ON TABLE sandbox_conversation IS
  'Reviewer test conversations. A SEPARATE table, not a flag on conversations, so no analytics or modeler query can include them by forgetting a filter.';

-- ---------------------------------------------------------------------------
-- 3. Device push tokens.
--
--    Created now and written by nobody: push needs a native module and a new
--    build, so it ships in a later wave. The table lands here so the wave-2
--    change is code only, and so right-to-delete parity is settled while the
--    schema change is in front of someone.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS device_push_token (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  token       TEXT NOT NULL,
  platform    TEXT NOT NULL CHECK (platform IN ('ios', 'android')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT device_push_token_unique UNIQUE (user_id, token)
);

CREATE INDEX IF NOT EXISTS device_push_token_user_idx ON device_push_token (user_id);
ALTER TABLE device_push_token ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE device_push_token IS
  'Expo push tokens per device. A persistent device identifier, so it is user data: delete_all_user_data() must clear it (repo rule, enforced by tests/test_connection_map_migrations.py).';

-- ---------------------------------------------------------------------------
-- 4. Deciding an application is a FUNCTION, not an UPDATE.
--
--    sage_review holds SELECT only on reviewer, deliberately: granting it write
--    turns the exclusivity trigger's error message into a patient-existence
--    oracle (.claude/rules/connection-map.md). So the admin cannot approve by
--    updating a row, and this is modelled on connection_map_attest — SECURITY
--    DEFINER, caller identified by AUTH USER ID rather than a reviewer id the
--    caller could supply, and the audit row written in the same transaction as
--    the status change so no path activates a reviewer without a trace.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_decide_reviewer_application(
  p_reviewer_id       UUID,
  p_admin_auth_user_id UUID,
  p_decision          TEXT,
  p_note              TEXT DEFAULT NULL
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_admin_id     UUID;
  v_admin_role   TEXT;
  v_admin_status TEXT;
  v_status       TEXT;
  v_new_status   TEXT;
BEGIN
  IF p_decision NOT IN ('approve', 'reject') THEN
    RAISE EXCEPTION 'connection_map: decision must be approve or reject';
  END IF;

  SELECT r.id, r.role, r.status
    INTO v_admin_id, v_admin_role, v_admin_status
    FROM reviewer r
   WHERE r.auth_user_id = p_admin_auth_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: no reviewer for this account';
  END IF;
  IF v_admin_role <> 'admin' OR v_admin_status <> 'active' THEN
    RAISE EXCEPTION 'connection_map: only an active admin may decide an application';
  END IF;
  IF v_admin_id = p_reviewer_id THEN
    -- Nobody activates themselves, even holding admin.
    RAISE EXCEPTION 'connection_map: an admin cannot decide their own application';
  END IF;

  SELECT status INTO v_status FROM reviewer WHERE id = p_reviewer_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: reviewer % not found', p_reviewer_id;
  END IF;
  IF v_status NOT IN ('requested', 'invited') THEN
    RAISE EXCEPTION
      'connection_map: this application is already %, there is nothing to decide', v_status;
  END IF;

  v_new_status := CASE WHEN p_decision = 'approve' THEN 'active' ELSE 'revoked' END;

  UPDATE reviewer
     SET status       = v_new_status,
         -- reviewer_active_has_timestamp_check requires this on activation.
         activated_at = CASE WHEN v_new_status = 'active' THEN NOW() ELSE activated_at END,
         decided_at   = NOW(),
         decided_by   = v_admin_id,
         decision_note = p_note,
         updated_at   = NOW()
   WHERE id = p_reviewer_id;

  -- A reviewer without a sandbox has a chat with nothing behind it, so it is
  -- created in the same transaction as the activation rather than lazily.
  IF v_new_status = 'active' THEN
    INSERT INTO sandbox_patient (reviewer_id)
    VALUES (p_reviewer_id)
    ON CONFLICT (reviewer_id) DO NOTHING;
  END IF;

  INSERT INTO audit_log (actor_id, actor_role, action, target_table, target_id, metadata)
  VALUES (v_admin_id, 'admin', 'reviewer_' || p_decision, 'reviewer',
          p_reviewer_id::TEXT,
          jsonb_build_object('new_status', v_new_status, 'note', p_note));

  RETURN v_new_status;
END;
$$;

COMMENT ON FUNCTION connection_map_decide_reviewer_application(UUID, UUID, TEXT, TEXT) IS
  'Approves or rejects a reviewer application. SECURITY DEFINER because sage_review holds SELECT only on reviewer by design. Takes the ADMIN AUTH USER ID, not a reviewer id, so the decider is the one the caller token proved. Creates the sandbox patient and writes audit_log in the same transaction.';

REVOKE ALL ON FUNCTION connection_map_decide_reviewer_application(UUID, UUID, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION connection_map_decide_reviewer_application(UUID, UUID, TEXT, TEXT) FROM anon;
REVOKE ALL ON FUNCTION connection_map_decide_reviewer_application(UUID, UUID, TEXT, TEXT) FROM authenticated;
GRANT EXECUTE ON FUNCTION connection_map_decide_reviewer_application(UUID, UUID, TEXT, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION connection_map_decide_reviewer_application(UUID, UUID, TEXT, TEXT) TO sage_review;

-- The admin dashboard lists applications, so the review role needs to read the
-- credential columns it already holds SELECT on. No new write grant.
GRANT SELECT ON sandbox_patient TO sage_review;

-- ---------------------------------------------------------------------------
-- 5. Backfill: every reviewer who is already active gets a sandbox.
--
--    Without this, an existing reviewer lands in the app after this ships and
--    opens a chat with no patient behind it. Dr Csiki is active right now.
-- ---------------------------------------------------------------------------
INSERT INTO sandbox_patient (reviewer_id)
SELECT r.id FROM reviewer r WHERE r.status = 'active'
ON CONFLICT (reviewer_id) DO NOTHING;
