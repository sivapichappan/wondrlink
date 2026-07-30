-- Migration: connection_map — a second source may corroborate an existing edge
-- Date: 2026-08-01
-- Author: Connection map Phase 4 (SPEC-connection-map.md §4.4; owner decision D7)
--
-- WHAT WAS WRONG. Extraction could only ever CREATE an edge. When a second
-- document stated a relationship the map already held, the candidate was
-- discarded as a duplicate — 72 times in the first full pass-1 sweep. Those 72
-- were not noise: they were independent sources saying the same thing, which is
-- exactly the corroboration D7 asks for ("peer-reviewed sources corroborate but
-- never carry a connection alone"). A physician reviewing an edge backed by four
-- guidelines is in a different position from one reviewing an edge backed by a
-- single sentence, and the schema already supports it: master_edge_evidence is
-- many-per-edge and always was.
--
-- WHY A FUNCTION AND NOT A PLAIN INSERT. Two reasons, both about not breaking
-- something already load-bearing.
--
--   1. ORDINAL. master_edge_evidence has UNIQUE (master_edge_id, ordinal). A
--      caller computing "next ordinal" with a SELECT and then an INSERT races
--      with itself. The function reads it under a row lock on the edge.
--
--   2. ATTESTATION. connection_map_edge_hash covers EVERY evidence row, so
--      adding one to a signed edge changes the hash and the publication gate
--      then refuses the edge — a physician's signature silently voided by a
--      batch job. So this function writes only to a 'candidate' edge and
--      refuses every other status outright, with a message that says why.
--      'approved' has a signature to protect, 'rejected' was a clinical
--      decision that must not be reopened by a script, and nothing in the
--      codebase sets 'in_review' today (grep: it appears only in enums and
--      filters), so refusing it costs nothing and stays honest.
--
-- KNOWN LIMITATION, recorded rather than papered over. connection_map_attest
-- computes edge_hash server-side at signing time; the client does not send the
-- hash it had on screen. A reviewer who loads a candidate, and has evidence
-- added underneath them before they sign, signs a hash covering a row they did
-- not read. Restricting this function to 'candidate' edges does NOT close that
-- race, because candidates are precisely what reviewers read. The real fix is
-- optimistic concurrency — the queue returns edge_hash, the client sends it
-- back, and connection_map_attest refuses a mismatch — which is a change to the
-- attest function, the review API, and the mobile client, and belongs with them
-- rather than here. Until then the mitigation is operational: extraction runs
-- are batch jobs, not concurrent with review sessions.
--
-- Applied to sage-dev only. Prod is untouched.

-- ---------------------------------------------------------------------------
-- 1. The same quotation cannot be recorded twice on the same edge.
--
--    Makes a re-run idempotent: the second pass over a document that already
--    corroborated an edge adds nothing rather than piling up identical rows.
--
--    PARTIAL, on verbatim rows only, and deliberately so. A verbatim row is
--    identified by where it points (section + offset); two of them at the same
--    place on the same edge are the same citation. An `inferred` row (tier C)
--    has quoted_sentence NULL and carries its meaning in `reasoning`, so two
--    inferred rows citing one section are not necessarily duplicates and this
--    index must not decide that they are.
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS master_edge_evidence_one_quote_per_place
  ON master_edge_evidence (master_edge_id, source_section_id, char_offset)
  WHERE evidence_kind = 'verbatim';

COMMENT ON INDEX master_edge_evidence_one_quote_per_place IS
  'One verbatim citation per (edge, section, offset), so re-running extraction corroborates idempotently instead of duplicating evidence. Partial: inferred (tier C) rows carry their meaning in reasoning, not in a location.';

-- ---------------------------------------------------------------------------
-- 2. add_evidence_to_master_edge()
--
--    Returns the new evidence id, or NULL when that citation was already
--    recorded — so a caller can tell "corroborated" from "already knew".
--
--    SECURITY INVOKER, like insert_master_edge_with_evidence: the caller's own
--    privileges apply, and sage_review holds no INSERT on master_edge_evidence.
--    A reviewer session therefore cannot reach this even by calling it directly.
--
--    Every existing guard on the table still fires, because this is an ordinary
--    INSERT: the verify trigger checks the quotation character for character
--    against source_section, the tier/kind trigger keeps verbatim and inferred
--    honest, and the published-edge trigger refuses evidence on anything already
--    live. This function adds the two rules that are specific to corroboration
--    and delegates the rest.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION add_evidence_to_master_edge(
  p_master_edge_id UUID,
  p_evidence       JSONB
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_status  TEXT;
  v_ordinal INT;
  v_id      UUID;
BEGIN
  IF p_evidence IS NULL OR jsonb_typeof(p_evidence) <> 'object' THEN
    RAISE EXCEPTION 'connection_map: p_evidence must be a single JSON object';
  END IF;

  -- FOR UPDATE: holds the edge still while the ordinal is computed, so two
  -- concurrent corroborations cannot pick the same one.
  SELECT status INTO v_status
    FROM master_edge
   WHERE id = p_master_edge_id
     FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: master_edge % not found', p_master_edge_id;
  END IF;

  IF v_status <> 'candidate' THEN
    RAISE EXCEPTION
      'connection_map: cannot add evidence to a % edge (only candidate); an approved edge has a signature bound to its current evidence and a rejected one was a clinical decision',
      v_status;
  END IF;

  SELECT COALESCE(MAX(ordinal), -1) + 1 INTO v_ordinal
    FROM master_edge_evidence
   WHERE master_edge_id = p_master_edge_id;

  INSERT INTO master_edge_evidence (
    master_edge_id, source_section_id, source_document_id, section_ref,
    evidence_kind, quoted_sentence, reasoning, char_offset, ordinal
  )
  VALUES (
    p_master_edge_id,
    (p_evidence->>'source_section_id')::UUID,
    (p_evidence->>'source_document_id')::UUID,
    p_evidence->>'section_ref',
    COALESCE(p_evidence->>'evidence_kind', 'verbatim'),
    p_evidence->>'quoted_sentence',
    p_evidence->>'reasoning',
    COALESCE((p_evidence->>'char_offset')::INT, 0),
    v_ordinal
  )
  ON CONFLICT (master_edge_id, source_section_id, char_offset)
    WHERE evidence_kind = 'verbatim'
    DO NOTHING
  RETURNING id INTO v_id;

  -- NULL means the conflict clause fired: this citation was already on the
  -- edge. That is a normal outcome of a re-run, not an error.
  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION add_evidence_to_master_edge(UUID, JSONB) IS
  'Adds one corroborating evidence row to a CANDIDATE edge, allocating the next ordinal under a row lock. Returns the evidence id, or NULL if that citation was already recorded. Refuses approved/rejected/in_review edges: edge_hash covers every evidence row, so adding one to a signed edge would void the attestation.';

REVOKE ALL ON FUNCTION add_evidence_to_master_edge(UUID, JSONB) FROM PUBLIC;
REVOKE ALL ON FUNCTION add_evidence_to_master_edge(UUID, JSONB) FROM anon;
REVOKE ALL ON FUNCTION add_evidence_to_master_edge(UUID, JSONB) FROM authenticated;
GRANT EXECUTE ON FUNCTION add_evidence_to_master_edge(UUID, JSONB) TO service_role;
