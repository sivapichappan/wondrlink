-- Migration: connection_map — tier C, redefined and kept
-- Date: 2026-07-30
-- Author: Owner decision D2 (PLAN.md), superseding SPEC §4.4's tier C rule
--
-- SPEC §4.4 defines tier C as "no verifiable quotation. Discarded, never
-- queued", and Phase 1 enforced that by refusing to store one at all. The
-- owner redefined it: a tier C connection is a far-fetched, non-verbatim
-- relationship that may hold real insight or may be useless, kept in a
-- low-priority queue a physician looks at when they have time. An approved
-- tier C edge MAY reach a patient, through exactly the same attestation gate
-- as A and B — C changes what may be PROPOSED, never what may bypass review.
--
-- WHAT MUST STAY TRUE. "The system never fabricates a citation" is the
-- property that protects patients; "every row is verbatim" was only ever a
-- means to it. So tier C edges still point at REAL source sections — the
-- passages the inference came from — and may never present an invented
-- sentence as a quotation. That distinction becomes explicit here:
--
--   evidence_kind = 'verbatim'  → quoted_sentence must match the section text
--                                 character for character (the existing
--                                 trigger, unchanged). Tiers A and B accept
--                                 ONLY this kind.
--   evidence_kind = 'inferred'  → carries the model's reasoning and a real
--                                 section reference, and NO quotation claim.
--                                 quoted_sentence must be NULL, so there is
--                                 nothing that could be mistaken for a quote.
--
-- Tier C therefore cannot smuggle an unverified quotation through: an
-- 'inferred' row has no quotation at all, and a 'verbatim' row is still
-- checked exactly. Tier A/B are unaffected by this migration.
--
-- SEPARATE, STILL OPEN: tier C has no attorney-approved attestation wording.
-- The v1 sentence says the statement is "consistent with the cited sources",
-- which overclaims for an inference. config/connection_map/attestation_text.yaml
-- deliberately has no tier_c entry, and the API refuses to sign one (409).
-- That refusal is the gate keeping tier C away from patients until legal
-- signs off; this migration only lets tier C EXIST and be reviewed.

-- ---------------------------------------------------------------------------
-- 1. Allow tier C to be stored.
-- ---------------------------------------------------------------------------
ALTER TABLE master_edge DROP CONSTRAINT IF EXISTS master_edge_tier_check;
ALTER TABLE master_edge
  ADD CONSTRAINT master_edge_tier_check CHECK (tier IN ('A','B','C'));

-- ---------------------------------------------------------------------------
-- 2. Distinguish a quotation from an inference.
-- ---------------------------------------------------------------------------
ALTER TABLE master_edge_evidence
  ADD COLUMN IF NOT EXISTS evidence_kind TEXT NOT NULL DEFAULT 'verbatim';
ALTER TABLE master_edge_evidence
  ADD COLUMN IF NOT EXISTS reasoning TEXT;

ALTER TABLE master_edge_evidence DROP CONSTRAINT IF EXISTS master_edge_evidence_kind_check;
ALTER TABLE master_edge_evidence
  ADD CONSTRAINT master_edge_evidence_kind_check
  CHECK (evidence_kind IN ('verbatim','inferred'));

-- A verbatim row carries a quotation; an inferred row carries reasoning and
-- NO quotation. Stated both ways so an inferred row cannot hold a sentence
-- that later reads as a quote.
ALTER TABLE master_edge_evidence DROP CONSTRAINT IF EXISTS master_edge_evidence_quote_shape_check;
ALTER TABLE master_edge_evidence
  ADD CONSTRAINT master_edge_evidence_quote_shape_check
  CHECK (
    (evidence_kind = 'verbatim'
       AND quoted_sentence IS NOT NULL AND char_length(quoted_sentence) > 0)
    OR
    (evidence_kind = 'inferred'
       AND quoted_sentence IS NULL
       AND reasoning IS NOT NULL AND btrim(reasoning) <> '')
  );

-- quoted_sentence was NOT NULL with its own length CHECK; an inferred row
-- needs it NULL, and the shape constraint above now owns both rules.
ALTER TABLE master_edge_evidence ALTER COLUMN quoted_sentence DROP NOT NULL;
ALTER TABLE master_edge_evidence
  DROP CONSTRAINT IF EXISTS master_edge_evidence_quoted_sentence_check;

-- ---------------------------------------------------------------------------
-- 3. Verbatim verification runs on verbatim rows only — and is UNCHANGED for
--    them. An inferred row skips the quote comparison because it makes no
--    quotation claim, but still has its section and document cross-checked,
--    so it cannot point at a source that does not exist.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_verify_evidence()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  v_text        TEXT;
  v_document_id UUID;
  v_section_ref TEXT;
BEGIN
  SELECT s.text, s.document_id, s.section_ref
    INTO v_text, v_document_id, v_section_ref
    FROM source_section s
   WHERE s.id = NEW.source_section_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'connection_map: source_section % not found', NEW.source_section_id;
  END IF;

  IF v_document_id <> NEW.source_document_id THEN
    RAISE EXCEPTION 'connection_map: evidence document does not match its section document';
  END IF;

  IF v_section_ref <> NEW.section_ref THEN
    RAISE EXCEPTION 'connection_map: evidence section_ref does not match its section';
  END IF;

  IF NEW.evidence_kind = 'inferred' THEN
    -- No quotation claim to verify. The shape constraint guarantees
    -- quoted_sentence IS NULL here, so nothing can masquerade as a quote.
    RETURN NEW;
  END IF;

  IF substr(v_text, NEW.char_offset + 1, char_length(NEW.quoted_sentence))
     IS DISTINCT FROM NEW.quoted_sentence THEN
    RAISE EXCEPTION
      'connection_map: quoted_sentence does not match section text at offset %',
      NEW.char_offset;
  END IF;

  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- 4. Tier A and B accept verbatim evidence ONLY. Without this, the tier that
--    means "stated outright in one sentence" could quietly rest on inference.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_tier_evidence_kind()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  v_tier TEXT;
BEGIN
  SELECT tier INTO v_tier FROM master_edge WHERE id = NEW.master_edge_id;
  IF v_tier IN ('A','B') AND NEW.evidence_kind <> 'verbatim' THEN
    RAISE EXCEPTION
      'connection_map: tier % requires verbatim evidence, got %', v_tier, NEW.evidence_kind;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS master_edge_evidence_tier_kind ON master_edge_evidence;
CREATE TRIGGER master_edge_evidence_tier_kind
  BEFORE INSERT OR UPDATE OF evidence_kind, master_edge_id ON master_edge_evidence
  FOR EACH ROW EXECUTE FUNCTION connection_map_tier_evidence_kind();

-- ---------------------------------------------------------------------------
-- 5. The edge hash must cover the new fields, or changing an inference's
--    reasoning after signing would not void the signature (acceptance #10).
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

  SELECT coalesce(string_agg(
           concat_ws('|', ev.source_section_id, ev.section_ref,
                          ev.evidence_kind,
                          coalesce(ev.quoted_sentence, ''),
                          coalesce(ev.reasoning, ''),
                          ev.char_offset),
           E'\n' ORDER BY ev.ordinal, ev.id), '')
    INTO v_evidence
    FROM master_edge_evidence ev
   WHERE ev.master_edge_id = p_edge_id;

  RETURN encode(sha256((v_edge || E'\n--\n' || v_evidence)::bytea), 'hex');
END;
$$;

-- ---------------------------------------------------------------------------
-- 6. The publication gate's evidence re-check must skip inferred rows the same
--    way the insert trigger does, or a published tier C edge would be reported
--    as "evidence no longer matches its source text" forever.
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
  latest AS (
    SELECT DISTINCT ON (a.master_edge_id)
           a.master_edge_id, a.decision, a.edge_hash, a.reviewer_role,
           a.reviewer_credential, a.reviewer_status, a.signed_at
      FROM attestation a
      JOIN ver_edges ve ON ve.id = a.master_edge_id
     ORDER BY a.master_edge_id, a.signed_at DESC, a.id DESC
  )
  SELECT problems.id, problems.problem FROM (
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

    -- Verbatim rows only: an inferred row makes no quotation claim.
    UNION ALL
    SELECT e.id, 'evidence no longer matches its source text'
      FROM ver_edges ve
      JOIN master_edge e ON e.id = ve.id
      JOIN master_edge_evidence ev ON ev.master_edge_id = e.id
      JOIN source_section s ON s.id = ev.source_section_id
     WHERE ev.evidence_kind = 'verbatim'
       AND substr(s.text, ev.char_offset + 1, char_length(ev.quoted_sentence))
           IS DISTINCT FROM ev.quoted_sentence

    -- Tier A/B must rest on verbatim evidence, checked again here in case a
    -- row was retiered after its evidence was written.
    UNION ALL
    SELECT e.id, 'tier ' || e.tier || ' edge has inferred evidence'
      FROM ver_edges ve
      JOIN master_edge e ON e.id = ve.id
      JOIN master_edge_evidence ev ON ev.master_edge_id = e.id
     WHERE e.tier IN ('A','B') AND ev.evidence_kind <> 'verbatim'

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

    UNION ALL
    SELECT l.master_edge_id, 'attested by a reviewer who was ' || l.reviewer_status || ' at signing'
      FROM latest l WHERE l.reviewer_status <> 'active'

    UNION ALL
    SELECT l.master_edge_id, 'attested by role ' || l.reviewer_role || ', not reviewer_attesting'
      FROM latest l WHERE l.reviewer_role <> 'reviewer_attesting'

    UNION ALL
    SELECT l.master_edge_id, 'attested by credential ' || l.reviewer_credential
      FROM latest l WHERE l.reviewer_credential NOT IN ('MD','DO')

    UNION ALL
    SELECT l.master_edge_id, 'attestation voided: edge or evidence changed after signing'
      FROM latest l
     WHERE l.edge_hash IS DISTINCT FROM connection_map_edge_hash(l.master_edge_id)
  ) AS problems(id, problem);
END;
$$;

COMMENT ON COLUMN master_edge_evidence.evidence_kind IS
  'verbatim = a quotation verified character for character; inferred = a real section reference plus reasoning, with NO quotation claim (tier C only).';

-- ---------------------------------------------------------------------------
-- 7. The edge-creation RPC must be able to write the new fields, or extraction
--    could never create a tier C edge at all (its evidence would default to
--    'verbatim' with no quotation and fail the shape constraint).
--    Defaults keep every existing caller working unchanged.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION insert_master_edge_with_evidence(p_edge JSONB, p_evidence JSONB)
RETURNS UUID
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_edge_id UUID;
  v_row     JSONB;
  v_i       INT := 0;
BEGIN
  IF p_evidence IS NULL OR jsonb_typeof(p_evidence) <> 'array'
     OR jsonb_array_length(p_evidence) = 0 THEN
    RAISE EXCEPTION 'connection_map: at least one evidence row is required';
  END IF;

  INSERT INTO master_edge (
    src_concept_id, dst_concept_id, relationship, urgency, tier, status,
    candidate_origin, extraction_run_id, extraction_pass,
    prior_alpha, prior_beta, expected_prevalence_low, expected_prevalence_high,
    patient_phrasing, rejection_reason
  )
  VALUES (
    (p_edge->>'src_concept_id')::UUID,
    (p_edge->>'dst_concept_id')::UUID,
    p_edge->>'relationship',
    COALESCE(p_edge->>'urgency', 'routine'),
    p_edge->>'tier',
    COALESCE(p_edge->>'status', 'candidate'),
    p_edge->>'candidate_origin',
    (p_edge->>'extraction_run_id')::UUID,
    (p_edge->>'extraction_pass')::INT,
    COALESCE((p_edge->>'prior_alpha')::INT, 2),
    COALESCE((p_edge->>'prior_beta')::INT, 1),
    (p_edge->>'expected_prevalence_low')::NUMERIC,
    (p_edge->>'expected_prevalence_high')::NUMERIC,
    p_edge->>'patient_phrasing',
    p_edge->>'rejection_reason'
  )
  RETURNING id INTO v_edge_id;

  FOR v_row IN SELECT * FROM jsonb_array_elements(p_evidence) LOOP
    INSERT INTO master_edge_evidence (
      master_edge_id, source_section_id, source_document_id, section_ref,
      evidence_kind, quoted_sentence, reasoning, char_offset, ordinal
    )
    VALUES (
      v_edge_id,
      (v_row->>'source_section_id')::UUID,
      (v_row->>'source_document_id')::UUID,
      v_row->>'section_ref',
      COALESCE(v_row->>'evidence_kind', 'verbatim'),
      v_row->>'quoted_sentence',
      v_row->>'reasoning',
      COALESCE((v_row->>'char_offset')::INT, 0),
      COALESCE((v_row->>'ordinal')::INT, v_i)
    );
    v_i := v_i + 1;
  END LOOP;

  RETURN v_edge_id;
END;
$$;

REVOKE ALL ON FUNCTION insert_master_edge_with_evidence(JSONB, JSONB) FROM PUBLIC;
REVOKE ALL ON FUNCTION insert_master_edge_with_evidence(JSONB, JSONB) FROM anon;
REVOKE ALL ON FUNCTION insert_master_edge_with_evidence(JSONB, JSONB) FROM authenticated;
GRANT EXECUTE ON FUNCTION insert_master_edge_with_evidence(JSONB, JSONB) TO service_role;
