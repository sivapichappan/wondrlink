-- Migration: connection_map — attestation records and the edge hash
-- Date: 2026-07-29
-- Author: Connection map Phase 3 (SPEC-connection-map.md §5.6, acceptance #10, #25)
--
-- An attestation is a physician putting their name to a specific statement
-- backed by specific evidence. It is the only thing standing between an LLM's
-- output and a patient, so it is immutable, it snapshots who signed and in what
-- capacity, and it is bound to the exact content that was on screen when they
-- signed.
--
-- HOW "EDITING VOIDS THE ATTESTATION" (§5.6, acceptance #10) WORKS. Signing
-- records edge_hash: a digest over the edge's meaningful fields AND every one
-- of its evidence rows. Change either afterwards and the recomputed hash stops
-- matching, so the publication gate refuses the edge. No trigger has to chase
-- edits around the schema; the hash simply stops agreeing, which is harder to
-- get wrong and impossible to forget.
--
-- WHY reviewer_status IS SNAPSHOTTED, beyond §5.6's field list. Acceptance #7
-- and #8 turn on the reviewer's standing AT SIGNING: publication must fail if
-- they were revoked then, and must SUCCEED if they were active then and were
-- revoked later. The reviewer table holds only current status, so signing-time
-- standing has to be captured at signing or it is unknowable afterwards.

-- ---------------------------------------------------------------------------
-- The edge hash. Deterministic, ordered, and covering evidence.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_edge_hash(p_edge_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
  v_edge     TEXT;
  v_evidence TEXT;
BEGIN
  -- Only fields whose change should invalidate a signature. created_at,
  -- updated_at and status are deliberately excluded: moving an edge from
  -- candidate to approved is what signing DOES, and must not void the
  -- signature it is part of.
  SELECT concat_ws('|',
           e.src_concept_id, e.dst_concept_id, e.relationship,
           e.urgency, e.tier, e.candidate_origin,
           coalesce(e.patient_phrasing, ''),
           coalesce(e.expected_prevalence_low::TEXT, ''),
           coalesce(e.expected_prevalence_high::TEXT, ''))
    INTO v_edge
    FROM master_edge e
   WHERE e.id = p_edge_id;

  IF v_edge IS NULL THEN
    RAISE EXCEPTION 'connection_map: master_edge % not found', p_edge_id;
  END IF;

  -- Ordered so the digest is stable; every evidence row participates, so
  -- adding, removing or editing one changes the hash.
  SELECT coalesce(string_agg(
           concat_ws('|', ev.source_section_id, ev.section_ref,
                          ev.quoted_sentence, ev.char_offset),
           E'\n' ORDER BY ev.ordinal, ev.id), '')
    INTO v_evidence
    FROM master_edge_evidence ev
   WHERE ev.master_edge_id = p_edge_id;

  RETURN encode(sha256((v_edge || E'\n--\n' || v_evidence)::bytea), 'hex');
END;
$$;

-- ---------------------------------------------------------------------------
-- attestation
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attestation (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  master_edge_id           UUID NOT NULL REFERENCES master_edge(id) ON DELETE RESTRICT,
  reviewer_id              UUID NOT NULL REFERENCES reviewer(id) ON DELETE RESTRICT,
  -- Capacity at signing time. Snapshotted, not joined: what matters is what
  -- they were when they signed, not what they are now.
  reviewer_role            TEXT NOT NULL CHECK (reviewer_role IN (
                             'observer','reviewer_clinical','reviewer_attesting','admin')),
  reviewer_credential      TEXT NOT NULL CHECK (reviewer_credential IN (
                             'MD','DO','NP','PA','PharmD','RN','other')),
  reviewer_affiliation     TEXT NOT NULL CHECK (reviewer_affiliation IN ('internal','external')),
  reviewer_status          TEXT NOT NULL CHECK (reviewer_status IN ('invited','active','revoked')),
  decision                 TEXT NOT NULL CHECK (decision IN ('approve','reject')),
  attestation_text_version TEXT NOT NULL,
  attestation_text         TEXT NOT NULL,
  edge_hash                TEXT NOT NULL,
  signed_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ip_hash                  TEXT,

  -- §5.1: only a physician may attest, restated here so a bad row cannot exist
  -- even if the reviewer row is later edited.
  CONSTRAINT attestation_is_physician_check
    CHECK (reviewer_role = 'reviewer_attesting' AND reviewer_credential IN ('MD','DO'))
);

CREATE INDEX IF NOT EXISTS attestation_edge_idx ON attestation (master_edge_id, signed_at DESC);
CREATE INDEX IF NOT EXISTS attestation_reviewer_idx ON attestation (reviewer_id);

-- Immutable (§5.6, acceptance #25). Reversing a decision means signing again;
-- both signatures stay in the trail.
DROP TRIGGER IF EXISTS attestation_append_only ON attestation;
CREATE TRIGGER attestation_append_only
  BEFORE UPDATE OR DELETE ON attestation
  FOR EACH ROW EXECUTE FUNCTION connection_map_block_write();

ALTER TABLE attestation ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Signing. A function rather than a plain INSERT so the snapshot and the hash
-- are taken by the database at the moment of signing, from live rows, and
-- cannot be supplied by a caller.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_attest(
  p_edge_id       UUID,
  p_reviewer_id   UUID,
  p_decision      TEXT,
  p_text_version  TEXT,
  p_text          TEXT,
  p_ip_hash       TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  v_role        TEXT;
  v_credential  TEXT;
  v_affiliation TEXT;
  v_status      TEXT;
  v_id          UUID;
BEGIN
  SELECT r.role, r.credential, r.affiliation, r.status
    INTO v_role, v_credential, v_affiliation, v_status
    FROM reviewer r
   WHERE r.id = p_reviewer_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: reviewer % not found', p_reviewer_id;
  END IF;

  -- Checked here as well as by the table CHECK so the error names the reason.
  IF v_role <> 'reviewer_attesting' THEN
    RAISE EXCEPTION 'connection_map: reviewer % may not attest (role %)', p_reviewer_id, v_role;
  END IF;
  IF v_status <> 'active' THEN
    RAISE EXCEPTION 'connection_map: reviewer % is not active (status %)', p_reviewer_id, v_status;
  END IF;

  INSERT INTO attestation (
    master_edge_id, reviewer_id, reviewer_role, reviewer_credential,
    reviewer_affiliation, reviewer_status, decision,
    attestation_text_version, attestation_text, edge_hash, ip_hash
  )
  VALUES (
    p_edge_id, p_reviewer_id, v_role, v_credential,
    v_affiliation, v_status, p_decision,
    p_text_version, p_text, connection_map_edge_hash(p_edge_id), p_ip_hash
  )
  RETURNING id INTO v_id;

  INSERT INTO audit_log (actor_id, actor_role, action, target_table, target_id, metadata)
  VALUES (p_reviewer_id, v_role, 'attest_' || p_decision, 'master_edge',
          p_edge_id::TEXT, jsonb_build_object('attestation_id', v_id));

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT) FROM anon;
REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT) FROM authenticated;
GRANT EXECUTE ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT) TO service_role;
-- The review client signs on the physician's behalf, so it needs this. It
-- still cannot forge the snapshot: every field comes from live rows.
GRANT EXECUTE ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT) TO sage_review;

GRANT SELECT ON attestation TO sage_review;
DROP POLICY IF EXISTS attestation_sage_review_select ON attestation;
CREATE POLICY attestation_sage_review_select ON attestation
  FOR SELECT TO sage_review USING (true);
-- INSERT goes through connection_map_attest only, never a direct write.

COMMENT ON TABLE attestation IS
  'Immutable physician signatures (SPEC 5.6). Snapshots signing-time capacity and binds to edge_hash, so editing the edge or its evidence voids the signature.';
COMMENT ON FUNCTION connection_map_edge_hash(UUID) IS
  'Digest over an edge and every one of its evidence rows. Excludes status: approving an edge must not void the signature that approves it.';
