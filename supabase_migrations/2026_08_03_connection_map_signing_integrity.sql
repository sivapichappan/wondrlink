-- Migration: connection_map — you cannot sign, or change, what you did not see
-- Date: 2026-08-03
-- Author: Connection map Phase 5 prep (SPEC-connection-map.md §5.6, acceptance #10)
--
-- Two holes in the same guarantee. §5.6 says an attestation is "bound to the exact
-- content that was on screen when they signed". Neither of these was true.
--
-- HOLE 1 — SIGNING SOMETHING THAT ARRIVED AFTER YOU READ IT.
-- connection_map_attest computed connection_map_edge_hash at the moment of signing,
-- from live rows. A reviewer opens a candidate, reads two quotations, and signs; if a
-- corroborating evidence row landed in between (add_evidence_to_master_edge does
-- exactly that, by design), the signature covers three quotations, one of which they
-- never saw. Nothing detected it, because the hash was computed from whatever was
-- there at the end rather than compared against what was there at the start.
--
-- Fixed by pinning: the queue hands out each edge's hash, the client sends it back,
-- and the function refuses if the edge has moved. p_expected_hash is REQUIRED, not
-- defaulted to NULL — a nullable check is one forgetful caller away from being no
-- check at all, and that is precisely the failure being closed.
--
-- HOLE 2 — EDITING AWAY A SIGNATURE THAT ALREADY EXISTS.
-- The review API's Reword handler updates master_edge with no status check at all, so
-- rewording an already-approved edge changes patient_phrasing, which IS hash-covered.
-- The signature silently stops matching. Nothing surfaces at the time; the edge simply
-- fails the publication gate later with "attestation voided", with nothing to say why
-- or when. That is reachable from the reviewer's own screen today.
--
-- Fixed with a trigger rather than a check in the handler, because it has to bind
-- every path — the API, a script, a manual query, a future endpoint nobody has written
-- yet. Application-layer guards protect the one door they are standing in front of.
--
-- WHAT IS DELIBERATELY STILL ALLOWED. status and rejection_reason are excluded from
-- the hash (2026_07_29_connection_map_attestation.sql:37-40): moving an edge from
-- candidate to approved is what signing DOES, and must not void the signature it is
-- part of. So the freeze below covers the hash-bearing columns only, and attesting
-- still works on an edge that already carries an attestation — a physician may change
-- their mind, and the later attestation wins by signed_at.
--
-- Applied to sage-dev only. Prod has never had these tables.

-- ---------------------------------------------------------------------------
-- 1. Hashes for a whole page in one round trip.
--
--    connection_map_edge_hash takes a single id. The review queue returns up to a
--    page of edges and now needs a hash for each, and a per-edge RPC would be one
--    network round trip per row through PostgREST. This is the same function,
--    applied set-wise.
--
--    SQL rather than plpgsql, and STABLE, so the planner can inline it.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_edge_hashes(p_edge_ids UUID[])
RETURNS TABLE(edge_id UUID, edge_hash TEXT)
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT e.id, connection_map_edge_hash(e.id)
    FROM master_edge e
   WHERE e.id = ANY(p_edge_ids);
$$;

COMMENT ON FUNCTION connection_map_edge_hashes(UUID[]) IS
  'Edge hashes for a whole queue page in one call. Same digest as connection_map_edge_hash, which the reviewer sends back when signing so the signature is pinned to what was on screen.';

REVOKE ALL ON FUNCTION connection_map_edge_hashes(UUID[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION connection_map_edge_hashes(UUID[]) FROM anon;
REVOKE ALL ON FUNCTION connection_map_edge_hashes(UUID[]) FROM authenticated;
GRANT EXECUTE ON FUNCTION connection_map_edge_hashes(UUID[]) TO service_role;
GRANT EXECUTE ON FUNCTION connection_map_edge_hashes(UUID[]) TO sage_review;

-- ---------------------------------------------------------------------------
-- 2. connection_map_attest gains p_expected_hash.
--
--    The 7-arg version is dropped rather than overloaded: leaving it in place would
--    keep a callable path that skips the check entirely.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT);

CREATE OR REPLACE FUNCTION connection_map_attest(
  p_edge_id       UUID,
  p_auth_user_id  UUID,
  p_decision      TEXT,
  p_text_version  TEXT,
  p_text          TEXT,
  p_expected_hash TEXT,
  p_ip_hash       TEXT DEFAULT NULL,
  p_rejection_reason TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_reviewer_id UUID;
  v_role        TEXT;
  v_credential  TEXT;
  v_affiliation TEXT;
  v_status      TEXT;
  v_actual_hash TEXT;
  v_id          UUID;
BEGIN
  IF p_decision NOT IN ('approve','reject') THEN
    RAISE EXCEPTION 'connection_map: decision must be approve or reject';
  END IF;

  SELECT r.id, r.role, r.credential, r.affiliation, r.status
    INTO v_reviewer_id, v_role, v_credential, v_affiliation, v_status
    FROM reviewer r
   WHERE r.auth_user_id = p_auth_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: no reviewer for this account';
  END IF;
  IF v_role <> 'reviewer_attesting' THEN
    RAISE EXCEPTION 'connection_map: this reviewer may not attest (role %)', v_role;
  END IF;
  IF v_status <> 'active' THEN
    RAISE EXCEPTION 'connection_map: this reviewer is not active (status %)', v_status;
  END IF;

  -- THE PIN. Under a row lock, and BEFORE the status UPDATE below, so the
  -- comparison reads the edge as the reviewer had it and cannot race a concurrent
  -- evidence insert. add_evidence_to_master_edge takes the same lock, so one of the
  -- two waits for the other rather than interleaving.
  IF p_expected_hash IS NULL OR btrim(p_expected_hash) = '' THEN
    RAISE EXCEPTION 'connection_map: a signature must state the edge it is pinned to';
  END IF;

  PERFORM 1 FROM master_edge WHERE id = p_edge_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: master_edge % not found', p_edge_id;
  END IF;

  v_actual_hash := connection_map_edge_hash(p_edge_id);
  IF v_actual_hash IS DISTINCT FROM p_expected_hash THEN
    -- STALE_EDGE is a marker the API matches on to answer 409 rather than 500.
    RAISE EXCEPTION
      'connection_map: STALE_EDGE this connection changed after it was opened; reload it and read it again before signing';
  END IF;

  -- The status change lives in here so it is ATOMIC with the signature. The API used
  -- to update master_edge and then call this function in a separate PostgREST
  -- request; a failure in between left an edge marked approved with nothing signed,
  -- while the UI reported "nothing was signed".
  IF p_decision = 'approve' THEN
    UPDATE master_edge
       SET status = 'approved', rejection_reason = NULL, updated_at = NOW()
     WHERE id = p_edge_id;
  ELSE
    IF p_rejection_reason IS NULL OR btrim(p_rejection_reason) = '' THEN
      RAISE EXCEPTION 'connection_map: a rejection needs a structured reason';
    END IF;
    UPDATE master_edge
       SET status = 'rejected', rejection_reason = p_rejection_reason, updated_at = NOW()
     WHERE id = p_edge_id;
  END IF;

  INSERT INTO attestation (
    master_edge_id, reviewer_id, reviewer_role, reviewer_credential,
    reviewer_affiliation, reviewer_status, decision,
    attestation_text_version, attestation_text, edge_hash, ip_hash
  )
  VALUES (
    p_edge_id, v_reviewer_id, v_role, v_credential,
    v_affiliation, v_status, p_decision,
    -- The verified hash, not a recomputation: identical by construction now, and it
    -- cannot drift from what was compared.
    p_text_version, p_text, v_actual_hash, p_ip_hash
  )
  RETURNING id INTO v_id;

  INSERT INTO audit_log (actor_id, actor_role, action, target_table, target_id, metadata)
  VALUES (v_reviewer_id, v_role, 'attest_' || p_decision, 'master_edge',
          p_edge_id::TEXT, jsonb_build_object('attestation_id', v_id));

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT) IS
  'Signs an edge and moves its status ATOMICALLY. SECURITY DEFINER because sage_review holds no INSERT on attestation by design: the function is the only writer, and every snapshot field is read from live rows. Takes the AUTH USER ID, not a reviewer id, so the credited signer is the one the caller token proved. p_expected_hash pins the signature to the edge the reviewer actually read; a mismatch raises STALE_EDGE.';

REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT) FROM anon;
REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT) FROM authenticated;
GRANT EXECUTE ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT) TO sage_review;

-- ---------------------------------------------------------------------------
-- 3. Once an edge is signed, its hash-bearing fields are frozen.
--
--    The column list below must stay identical to the one connection_map_edge_hash
--    digests. If a column is added there and not here, an edit to it voids
--    signatures silently again — which is the whole bug. A static test in
--    tests/test_connection_map_migrations.py compares the two lists.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_block_attested_edge_edit()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM attestation a WHERE a.master_edge_id = OLD.id)
     AND ROW(NEW.src_concept_id, NEW.dst_concept_id, NEW.relationship,
             NEW.urgency, NEW.tier, NEW.candidate_origin,
             NEW.patient_phrasing,
             NEW.expected_prevalence_low, NEW.expected_prevalence_high)
         IS DISTINCT FROM
         ROW(OLD.src_concept_id, OLD.dst_concept_id, OLD.relationship,
             OLD.urgency, OLD.tier, OLD.candidate_origin,
             OLD.patient_phrasing,
             OLD.expected_prevalence_low, OLD.expected_prevalence_high)
  THEN
    RAISE EXCEPTION
      'connection_map: SIGNED_EDGE this connection has been signed; changing its wording or meaning would void the attestation. Publish a new version instead';
  END IF;
  -- COALESCE, not NEW: this trigger is UPDATE-only today, but a BEFORE row trigger
  -- returning NULL cancels the operation in silence, and this repo has already
  -- shipped that bug once (2026_08_02_connection_map_delete_trigger_fix.sql).
  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS master_edge_signed_fields_frozen ON master_edge;
CREATE TRIGGER master_edge_signed_fields_frozen
  BEFORE UPDATE ON master_edge
  FOR EACH ROW EXECUTE FUNCTION connection_map_block_attested_edge_edit();

COMMENT ON FUNCTION connection_map_block_attested_edge_edit() IS
  'Freezes the hash-bearing columns of an edge once any attestation exists for it. status and rejection_reason stay editable: moving candidate to approved is what signing does. Column list must mirror connection_map_edge_hash exactly.';
