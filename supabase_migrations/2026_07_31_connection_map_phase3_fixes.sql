-- Migration: connection_map — Phase 3 fixes from adversarial review
-- Date: 2026-07-31
-- Author: Connection map (post-Phase-3 review)
--
-- Four defects, two of them severe. The first was invisible to the Phase 3
-- probe checklist because those probes ran as `postgres`, never as the role
-- the application actually uses. That is the lesson worth keeping: probing a
-- database function as a superuser proves the LOGIC, not the DEPLOYMENT.

-- ---------------------------------------------------------------------------
-- 1. SIGNING WAS COMPLETELY BROKEN IN PRODUCTION.
--
-- connection_map_attest was SECURITY INVOKER, so it inserted as its caller —
-- sage_review — which holds only SELECT on attestation. Every approval from
-- the workspace would have failed with "permission denied for table
-- attestation". Verified on sage-dev.
--
-- Fixed as SECURITY DEFINER, and deliberately WITHOUT granting sage_review
-- any INSERT on the table. The tradeoff, stated plainly:
--
--   * Granting INSERT instead would let a compromised review client write an
--     attestation row directly, forging the capacity snapshot and the
--     edge_hash — i.e. a signature that never corresponded to any content.
--   * SECURITY DEFINER keeps the function the ONLY writer, and every field
--     that matters (role, credential, affiliation, status, hash) is read from
--     live rows inside it, so none of them can be supplied by a caller.
--
-- The residual risk is WHO gets credited. That is why the parameter is now the
-- AUTH USER ID rather than a reviewer id: the value passed is the one the
-- caller's token proved, and the function resolves the reviewer itself.
-- Crediting a different physician now requires compromising the Flask app,
-- not merely calling the RPC with a different argument.
--
-- search_path is pinned, which for a DEFINER function is not optional.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT);

CREATE OR REPLACE FUNCTION connection_map_attest(
  p_edge_id       UUID,
  p_auth_user_id  UUID,
  p_decision      TEXT,
  p_text_version  TEXT,
  p_text          TEXT,
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

  -- 2. THE STATUS CHANGE MOVES IN HERE, so it is ATOMIC with the signature.
  -- The API used to update master_edge and then call this function in a
  -- separate PostgREST request; a failure in between left an edge marked
  -- approved with nothing signed, while the UI reported "nothing was signed".
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

  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: master_edge % not found', p_edge_id;
  END IF;

  INSERT INTO attestation (
    master_edge_id, reviewer_id, reviewer_role, reviewer_credential,
    reviewer_affiliation, reviewer_status, decision,
    attestation_text_version, attestation_text, edge_hash, ip_hash
  )
  VALUES (
    p_edge_id, v_reviewer_id, v_role, v_credential,
    v_affiliation, v_status, p_decision,
    p_text_version, p_text, connection_map_edge_hash(p_edge_id), p_ip_hash
  )
  RETURNING id INTO v_id;

  INSERT INTO audit_log (actor_id, actor_role, action, target_table, target_id, metadata)
  VALUES (v_reviewer_id, v_role, 'attest_' || p_decision, 'master_edge',
          p_edge_id::TEXT, jsonb_build_object('attestation_id', v_id));

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT) FROM anon;
REVOKE ALL ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT) FROM authenticated;
GRANT EXECUTE ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT) TO sage_review;

-- ---------------------------------------------------------------------------
-- 3. PUBLISHED CONTENT WAS NOT ACTUALLY IMMUTABLE.
--
-- §4.5's trigger froze the master_map_version ROW, but nothing stopped an edge
-- INSIDE a published version from being edited or re-attested, and frozen_hash
-- was never recomputed. So a reviewer could reword live patient-facing wording
-- after a physician signed it, or reject an edge a published version still
-- lists, with no signal anywhere. The publish screen's promise that publishing
-- "cannot be undone or edited afterwards" was false.
--
-- Enforced at the database because §16 asks for it and because the API is not
-- the only possible caller.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_edge_is_published(p_edge_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1 FROM master_map_version v
     WHERE v.status = 'published' AND p_edge_id = ANY(v.edge_ids)
  );
$$;

CREATE OR REPLACE FUNCTION connection_map_block_published_edge_edit()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF connection_map_edge_is_published(OLD.id) THEN
    RAISE EXCEPTION
      'connection_map: this edge is part of a published version and cannot be changed; publish a new version instead';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS master_edge_published_is_frozen ON master_edge;
CREATE TRIGGER master_edge_published_is_frozen
  BEFORE UPDATE OR DELETE ON master_edge
  FOR EACH ROW EXECUTE FUNCTION connection_map_block_published_edge_edit();

-- Evidence of a published edge is equally frozen: changing it would move the
-- edge hash out from under a signature that is already live.
CREATE OR REPLACE FUNCTION connection_map_block_published_evidence_edit()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  v_edge UUID;
BEGIN
  v_edge := COALESCE(NEW.master_edge_id, OLD.master_edge_id);
  IF connection_map_edge_is_published(v_edge) THEN
    RAISE EXCEPTION
      'connection_map: evidence for a published edge cannot be changed; publish a new version instead';
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS master_edge_evidence_published_is_frozen ON master_edge_evidence;
CREATE TRIGGER master_edge_evidence_published_is_frozen
  BEFORE INSERT OR UPDATE OR DELETE ON master_edge_evidence
  FOR EACH ROW EXECUTE FUNCTION connection_map_block_published_evidence_edit();

-- ---------------------------------------------------------------------------
-- 4. PUBLISH COULD RE-PUBLISH AN ALREADY-PUBLISHED OR SUPERSEDED VERSION,
--    rewriting published_at and frozen_hash and destroying the original
--    publication record. Only a draft may be published.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_publish(
  p_version_id  UUID,
  p_actor_id    UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  v_blockers TEXT;
  v_count    INT;
  v_cancer   TEXT;
  v_version  INT;
  v_status   TEXT;
  v_hash     TEXT;
BEGIN
  SELECT cancer, version, status INTO v_cancer, v_version, v_status
    FROM master_map_version WHERE id = p_version_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: map version % not found', p_version_id;
  END IF;
  IF v_status <> 'draft' THEN
    RAISE EXCEPTION
      'connection_map: only a draft can be published (this version is %)', v_status;
  END IF;

  SELECT count(*), string_agg(coalesce(edge_id::TEXT, 'version') || ': ' || problem, E'\n')
    INTO v_count, v_blockers
    FROM connection_map_publication_blockers(p_version_id);

  IF v_count > 0 THEN
    RAISE EXCEPTION E'connection_map: cannot publish, % blocker(s):\n%', v_count, v_blockers;
  END IF;

  SELECT encode(sha256(string_agg(connection_map_edge_hash(e), E'\n' ORDER BY e)::bytea), 'hex')
    INTO v_hash
    FROM unnest((SELECT edge_ids FROM master_map_version WHERE id = p_version_id)) AS e;

  UPDATE master_map_version
     SET status = 'superseded', updated_at = NOW()
   WHERE cancer = v_cancer AND status = 'published' AND id <> p_version_id;

  UPDATE master_map_version
     SET status = 'published', published_at = NOW(),
         published_by = p_actor_id, frozen_hash = v_hash, updated_at = NOW()
   WHERE id = p_version_id;

  INSERT INTO audit_log (actor_id, actor_role, action, target_table, target_id, after_hash, metadata)
  VALUES (p_actor_id, 'admin', 'publish', 'master_map_version', p_version_id::TEXT, v_hash,
          jsonb_build_object('cancer', v_cancer, 'version', v_version));

  RETURN p_version_id;
END;
$$;

REVOKE ALL ON FUNCTION connection_map_publish(UUID, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION connection_map_publish(UUID, UUID) FROM anon;
REVOKE ALL ON FUNCTION connection_map_publish(UUID, UUID) FROM authenticated;
GRANT EXECUTE ON FUNCTION connection_map_publish(UUID, UUID) TO service_role;
GRANT EXECUTE ON FUNCTION connection_map_publish(UUID, UUID) TO sage_review;

COMMENT ON FUNCTION connection_map_attest(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT) IS
  'Signs an edge and moves its status ATOMICALLY. SECURITY DEFINER because sage_review holds no INSERT on attestation by design: the function is the only writer, and every snapshot field is read from live rows. Takes the AUTH USER ID, not a reviewer id, so the credited signer is the one the caller token proved.';
