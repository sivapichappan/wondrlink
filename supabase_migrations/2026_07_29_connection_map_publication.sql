-- Migration: connection_map — the publication gate
-- Date: 2026-07-29
-- Author: Connection map Phase 3 (SPEC-connection-map.md §5.7, §5.10)
--
-- Publication is the moment content becomes eligible to reach a patient, so
-- every §5.7 condition is checked here, in one transaction, in the database.
-- There is no admin override and no force flag; §16 lists "admin override on
-- publication" among the things that have been asked for before and are
-- excluded on purpose.
--
-- The gate reports EVERY blocker at once rather than stopping at the first.
-- A physician's review time is the scarcest thing in this project, and sending
-- them round the loop once per problem wastes it.
--
-- Enabled relationship types are recorded per version (§4.3's "v1 enabled"
-- column, and §5.7's "no edge uses a type with enabled_in_version = false"),
-- so a version freezes which kinds of statement it may contain. v1 ships
-- side_effect_of and co_occurs_with.

ALTER TABLE master_map_version
  ADD COLUMN IF NOT EXISTS enabled_relationships TEXT[] NOT NULL
  DEFAULT ARRAY['side_effect_of','co_occurs_with'];

ALTER TABLE master_map_version
  DROP CONSTRAINT IF EXISTS master_map_version_enabled_relationships_check;
ALTER TABLE master_map_version
  ADD CONSTRAINT master_map_version_enabled_relationships_check
  CHECK (enabled_relationships <@ ARRAY[
           'side_effect_of','co_occurs_with','indicated_by',
           'monitored_with','mitigated_by','acts_through']::TEXT[]
         AND cardinality(enabled_relationships) > 0
         -- §4.3: a patient cannot validate a mediator, so this type is
         -- authoring-only and may never be enabled in a published version.
         AND NOT ('acts_through' = ANY(enabled_relationships)));

-- ---------------------------------------------------------------------------
-- The itemized check. One row per problem; empty means publishable.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_publication_blockers(p_version_id UUID)
RETURNS TABLE (edge_id UUID, problem TEXT)
LANGUAGE plpgsql
STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
  v_version master_map_version%ROWTYPE;
BEGIN
  SELECT * INTO v_version FROM master_map_version WHERE id = p_version_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: map version % not found', p_version_id;
  END IF;

  -- §5.7 and §5.10: a version cannot publish without its governance note.
  IF v_version.governance_note IS NULL OR btrim(v_version.governance_note) = '' THEN
    RETURN QUERY SELECT NULL::UUID, 'governance_note is required to publish'::TEXT;
  END IF;

  IF v_version.edge_ids IS NULL OR cardinality(v_version.edge_ids) = 0 THEN
    RETURN QUERY SELECT NULL::UUID, 'version contains no edges'::TEXT;
  END IF;

  RETURN QUERY
  WITH ver_edges AS (
    SELECT unnest(v_version.edge_ids) AS id
  ),
  -- The signature that counts is the most recent one per edge: reversing a
  -- decision means signing again (§5.6), and the later signature wins.
  latest AS (
    SELECT DISTINCT ON (a.master_edge_id)
           a.master_edge_id, a.decision, a.edge_hash, a.reviewer_role,
           a.reviewer_credential, a.reviewer_status, a.signed_at
      FROM attestation a
      JOIN ver_edges ve ON ve.id = a.master_edge_id
     ORDER BY a.master_edge_id, a.signed_at DESC, a.id DESC
  )
  SELECT problems.id, problems.problem FROM (
    -- referenced edge missing entirely
    SELECT ve.id, 'edge is not in master_edge'::TEXT AS problem
      FROM ver_edges ve LEFT JOIN master_edge e ON e.id = ve.id
     WHERE e.id IS NULL

    UNION ALL
    SELECT e.id, 'edge status is ' || e.status || ', expected approved'
      FROM ver_edges ve JOIN master_edge e ON e.id = ve.id
     WHERE e.status <> 'approved'

    UNION ALL
    SELECT e.id, 'relationship type ' || e.relationship || ' is not enabled in this version'
      FROM ver_edges ve JOIN master_edge e ON e.id = ve.id
     WHERE NOT (e.relationship = ANY(v_version.enabled_relationships))

    UNION ALL
    SELECT e.id, 'patient_phrasing is empty'
      FROM ver_edges ve JOIN master_edge e ON e.id = ve.id
     WHERE e.patient_phrasing IS NULL OR btrim(e.patient_phrasing) = ''

    UNION ALL
    SELECT e.id, 'edge has no evidence'
      FROM ver_edges ve JOIN master_edge e ON e.id = ve.id
     WHERE NOT EXISTS (SELECT 1 FROM master_edge_evidence ev WHERE ev.master_edge_id = e.id)

    -- §5.7: every evidence row must STILL verify against its source. The
    -- insert-time trigger cannot speak for a section re-ingested afterwards.
    UNION ALL
    SELECT e.id, 'evidence no longer matches its source text'
      FROM ver_edges ve
      JOIN master_edge e ON e.id = ve.id
      JOIN master_edge_evidence ev ON ev.master_edge_id = e.id
      JOIN source_section s ON s.id = ev.source_section_id
     WHERE substr(s.text, ev.char_offset + 1, char_length(ev.quoted_sentence))
           IS DISTINCT FROM ev.quoted_sentence

    UNION ALL
    SELECT e.id, 'concept ' || c.slug || ' has no display_patient'
      FROM ver_edges ve
      JOIN master_edge e ON e.id = ve.id
      JOIN concept c ON c.id IN (e.src_concept_id, e.dst_concept_id)
     WHERE c.display_patient IS NULL OR btrim(c.display_patient) = ''

    UNION ALL
    SELECT ve.id, 'edge has no attestation'
      FROM ver_edges ve LEFT JOIN latest l ON l.master_edge_id = ve.id
     WHERE l.master_edge_id IS NULL

    UNION ALL
    SELECT l.master_edge_id, 'most recent attestation is a rejection'
      FROM latest l WHERE l.decision <> 'approve'

    -- Acceptance #7 / #8: standing AT SIGNING, from the snapshot. A reviewer
    -- revoked afterwards does not invalidate what they signed while active.
    UNION ALL
    SELECT l.master_edge_id, 'attested by a reviewer who was ' || l.reviewer_status || ' at signing'
      FROM latest l WHERE l.reviewer_status <> 'active'

    UNION ALL
    SELECT l.master_edge_id, 'attested by role ' || l.reviewer_role || ', not reviewer_attesting'
      FROM latest l WHERE l.reviewer_role <> 'reviewer_attesting'

    UNION ALL
    SELECT l.master_edge_id, 'attested by credential ' || l.reviewer_credential
      FROM latest l WHERE l.reviewer_credential NOT IN ('MD','DO')

    -- Acceptance #10: the edge or its evidence changed after signing.
    UNION ALL
    SELECT l.master_edge_id, 'attestation voided: edge or evidence changed after signing'
      FROM latest l
     WHERE l.edge_hash IS DISTINCT FROM connection_map_edge_hash(l.master_edge_id)
  ) AS problems(id, problem);
END;
$$;

-- ---------------------------------------------------------------------------
-- Publish. Refuses with the full list, or freezes the version.
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
  v_hash     TEXT;
BEGIN
  SELECT count(*), string_agg(coalesce(edge_id::TEXT, 'version') || ': ' || problem, E'\n')
    INTO v_count, v_blockers
    FROM connection_map_publication_blockers(p_version_id);

  IF v_count > 0 THEN
    RAISE EXCEPTION E'connection_map: cannot publish, % blocker(s):\n%', v_count, v_blockers;
  END IF;

  SELECT cancer, version INTO v_cancer, v_version
    FROM master_map_version WHERE id = p_version_id;

  -- Freeze: a digest over every edge hash, in edge order, so the published
  -- content is pinned as a whole and not merely edge by edge.
  SELECT encode(sha256(string_agg(connection_map_edge_hash(e), E'\n' ORDER BY e)::bytea), 'hex')
    INTO v_hash
    FROM unnest((SELECT edge_ids FROM master_map_version WHERE id = p_version_id)) AS e;

  -- Supersede any previously published version for this cancer.
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
-- Publication is an admin action taken in the workspace, so the review client
-- may call it. The gate above is what actually decides, and it cannot be
-- argued with from the caller side.
GRANT EXECUTE ON FUNCTION connection_map_publish(UUID, UUID) TO sage_review;
GRANT EXECUTE ON FUNCTION connection_map_publication_blockers(UUID) TO sage_review;
GRANT EXECUTE ON FUNCTION connection_map_edge_hash(UUID) TO sage_review;

-- ---------------------------------------------------------------------------
-- §4.5: published versions are immutable. Deferred from Phase 1 until the
-- gate existed to define what publishing means; here it is.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_map_version_immutable()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF OLD.status = 'published' THEN
    -- The one permitted change: being superseded by a later version.
    IF NEW.status = 'superseded'
       AND NEW.cancer = OLD.cancer AND NEW.version = OLD.version
       AND NEW.edge_ids IS NOT DISTINCT FROM OLD.edge_ids
       AND NEW.frozen_hash IS NOT DISTINCT FROM OLD.frozen_hash
       AND NEW.published_at IS NOT DISTINCT FROM OLD.published_at
       AND NEW.governance_note IS NOT DISTINCT FROM OLD.governance_note THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'connection_map: published map versions are immutable';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS master_map_version_immutable ON master_map_version;
CREATE TRIGGER master_map_version_immutable
  BEFORE UPDATE ON master_map_version
  FOR EACH ROW EXECUTE FUNCTION connection_map_map_version_immutable();

COMMENT ON FUNCTION connection_map_publication_blockers(UUID) IS
  'Every §5.7 reason this version cannot publish, one row each. Empty means publishable.';
COMMENT ON FUNCTION connection_map_publish(UUID, UUID) IS
  'Publishes a version or raises with the full blocker list. No override exists, by design (SPEC §16).';
