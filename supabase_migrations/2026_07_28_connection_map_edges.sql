-- Migration: connection_map — master edges, evidence, extraction runs
-- Date: 2026-07-28
-- Author: Connection map Phase 1 (SPEC-connection-map.md §4.4, §13.1, PLAN.md)
--
-- HOUSE-STYLE DEPARTURE, DELIBERATE. Every other migration in this repo uses
-- only CREATE TABLE / CHECK / RLS. This one adds plpgsql functions and
-- triggers because the spec requires database-level enforcement (§16) and the
-- backend connects as the service role, which BYPASSES RLS. A CHECK or a
-- trigger binds the service role; an RLS policy does not. These are the two
-- invariants that carry the feature's entire credibility:
--
--   1. Every evidence row matches its section CHARACTER FOR CHARACTER (§4.4).
--      Exact string comparison only. Never relax this to fuzzy matching,
--      embeddings, or an LLM judge (§16) — the characteristic model failure is
--      a plausible relationship with an invented citation, and only exact
--      matching catches that every time.
--   2. An edge with zero evidence rows cannot exist (§4.4, acceptance #13).
--
-- Invariant 2 needs care on PostgREST, where every request is its own
-- transaction: a plain two-step insert (edge, then evidence) would leave the
-- edge naked between requests. So edge creation goes through the RPC
-- insert_master_edge_with_evidence(), which writes both atomically, and
-- DEFERRABLE INITIALLY DEFERRED constraint triggers make any other path fail
-- at COMMIT. Precedent for calling an RPC from the app: match_chunks
-- (lib/vector_search.py).
--
-- tier is CHECKed to ('A','B'), not the spec's ('A','B','C'): §4.4 defines
-- tier C as "no verifiable quotation. Discarded, never queued", so nothing may
-- legitimately persist one (PLAN.md decision #2). Widening a CHECK later is a
-- move this repo has made before.
--
-- Phase 2 adds reviewer/attestation/audit tables that reference master_edge.id
-- and owns status-transition enforcement; Phase 1 deliberately stops here.
--
-- Not patient data: RLS enabled, no policies (service role reaches it).

-- ---------------------------------------------------------------------------
-- extraction_run — implied infrastructure. §4.4 references extraction_run_id
-- but the spec never defines the table; this is the minimum that makes an
-- extraction batch attributable (which model, which prompt, what it produced).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS extraction_run (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cancer       TEXT NOT NULL,
  pass_number  INT NOT NULL DEFAULT 1 CHECK (pass_number BETWEEN 1 AND 3),
  model        TEXT,
  prompt_id    TEXT,           -- prompt file + SHA, matching the repo's pinned-prompt habit
  started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at  TIMESTAMPTZ,
  stats        JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- master_edge
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS master_edge (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  src_concept_id           UUID NOT NULL REFERENCES concept(id),
  dst_concept_id           UUID NOT NULL REFERENCES concept(id),
  relationship             TEXT NOT NULL CHECK (relationship IN (
                             'side_effect_of','co_occurs_with','indicated_by',
                             'monitored_with','mitigated_by','acts_through')),
  urgency                  TEXT NOT NULL DEFAULT 'routine'
                             CHECK (urgency IN ('routine','urgent')),
  tier                     TEXT NOT NULL CHECK (tier IN ('A','B')),
  status                   TEXT NOT NULL DEFAULT 'candidate'
                             CHECK (status IN ('candidate','in_review','approved','rejected')),
  candidate_origin         TEXT NOT NULL CHECK (candidate_origin IN (
                             'literature_scan','patient_observation')),
  extraction_run_id        UUID REFERENCES extraction_run(id),
  extraction_pass          INT CHECK (extraction_pass BETWEEN 1 AND 3),
  prior_alpha              INT NOT NULL DEFAULT 2 CHECK (prior_alpha > 0),
  prior_beta               INT NOT NULL DEFAULT 1 CHECK (prior_beta > 0),
  expected_prevalence_low  NUMERIC CHECK (expected_prevalence_low BETWEEN 0 AND 1),
  expected_prevalence_high NUMERIC CHECK (expected_prevalence_high BETWEEN 0 AND 1),
  patient_phrasing         TEXT,
  rejection_reason         TEXT CHECK (rejection_reason IN (
                             'quote_does_not_support','quote_out_of_context','too_general',
                             'wrong_relationship_type','not_appropriate_for_patients',
                             'clinically_incorrect','duplicate','chain_does_not_hold')),
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- A relationship from a concept to itself is never meaningful.
  CONSTRAINT master_edge_no_self_loop_check CHECK (src_concept_id <> dst_concept_id),
  -- Acceptance #26: every rejected edge carries a structured reason. Stated
  -- both ways so a reason cannot linger on an edge that is no longer rejected
  -- (the rejection mix is the extractor's only real eval signal, §13.1).
  CONSTRAINT master_edge_rejection_reason_check
    CHECK ((status = 'rejected') = (rejection_reason IS NOT NULL)),
  CONSTRAINT master_edge_prevalence_band_check
    CHECK (expected_prevalence_low IS NULL
           OR expected_prevalence_high IS NULL
           OR expected_prevalence_low <= expected_prevalence_high),
  -- A literature-scan candidate must be attributable to the run that made it.
  CONSTRAINT master_edge_scan_run_check
    CHECK (candidate_origin <> 'literature_scan' OR extraction_run_id IS NOT NULL),
  CONSTRAINT master_edge_triple_key UNIQUE (src_concept_id, dst_concept_id, relationship)
);

CREATE INDEX IF NOT EXISTS master_edge_dst_idx ON master_edge (dst_concept_id);
CREATE INDEX IF NOT EXISTS master_edge_status_idx ON master_edge (status);

-- ---------------------------------------------------------------------------
-- master_edge_evidence
--
-- source_section_id is the real anchor: the verify trigger reads the section
-- text by primary key, and ON DELETE RESTRICT means re-ingesting a document
-- that already has citations fails loudly instead of silently invalidating
-- them. source_document_id and section_ref are kept per §4.4 for display and
-- provenance; the trigger cross-checks them against the section row so they
-- cannot drift.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS master_edge_evidence (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  master_edge_id      UUID NOT NULL REFERENCES master_edge(id) ON DELETE CASCADE,
  source_section_id   UUID NOT NULL REFERENCES source_section(id) ON DELETE RESTRICT,
  source_document_id  UUID NOT NULL REFERENCES source_document(id),
  section_ref         TEXT NOT NULL,
  quoted_sentence     TEXT NOT NULL CHECK (char_length(quoted_sentence) > 0),
  char_offset         INT NOT NULL CHECK (char_offset >= 0),
  ordinal             INT NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT master_edge_evidence_ordinal_key UNIQUE (master_edge_id, ordinal)
);

CREATE INDEX IF NOT EXISTS master_edge_evidence_edge_idx ON master_edge_evidence (master_edge_id);
CREATE INDEX IF NOT EXISTS master_edge_evidence_section_idx ON master_edge_evidence (source_section_id);

-- ---------------------------------------------------------------------------
-- Trigger A — verbatim citation check (§4.4, §6.1, acceptance #11)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_verify_evidence()
RETURNS TRIGGER
LANGUAGE plpgsql
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

  -- char_offset is a 0-based code-point offset, so +1 for substr()'s 1-based
  -- start. Exact equality: no trimming, no case folding, no normalization.
  IF substr(v_text, NEW.char_offset + 1, char_length(NEW.quoted_sentence))
     IS DISTINCT FROM NEW.quoted_sentence THEN
    RAISE EXCEPTION
      'connection_map: quoted_sentence does not match section text at offset %',
      NEW.char_offset;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS master_edge_evidence_verify ON master_edge_evidence;
CREATE TRIGGER master_edge_evidence_verify
  BEFORE INSERT OR UPDATE OF quoted_sentence, char_offset, source_section_id,
                             source_document_id, section_ref
  ON master_edge_evidence
  FOR EACH ROW EXECUTE FUNCTION connection_map_verify_evidence();

-- ---------------------------------------------------------------------------
-- Trigger B — an edge with zero evidence cannot exist (§4.4, acceptance #13)
--
-- Deferred to COMMIT so the RPC below can insert the edge and its evidence in
-- one transaction, while any other path (a bare PostgREST insert, a manual
-- SQL statement) fails when its transaction ends.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION connection_map_edge_has_evidence()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_edge_id UUID;
  v_count   INT;
BEGIN
  -- Which row carries the edge id depends on which table fired: master_edge
  -- fires on INSERT (NEW), evidence fires on DELETE/UPDATE (OLD, so a row
  -- moved off an edge is checked against the edge it left). Branch rather
  -- than COALESCE: NEW is null in a DELETE trigger, and master_edge has no
  -- master_edge_id column, so a blanket field reference errors at runtime.
  IF TG_TABLE_NAME = 'master_edge' THEN
    v_edge_id := NEW.id;
  ELSE
    v_edge_id := OLD.master_edge_id;
  END IF;

  -- If the edge itself is gone, cascade removed its evidence legitimately.
  PERFORM 1 FROM master_edge WHERE id = v_edge_id;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  SELECT COUNT(*) INTO v_count FROM master_edge_evidence WHERE master_edge_id = v_edge_id;
  IF v_count = 0 THEN
    RAISE EXCEPTION
      'connection_map: master_edge % has no evidence; create edges via insert_master_edge_with_evidence()',
      v_edge_id;
  END IF;

  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS master_edge_requires_evidence ON master_edge;
CREATE CONSTRAINT TRIGGER master_edge_requires_evidence
  AFTER INSERT ON master_edge
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION connection_map_edge_has_evidence();

DROP TRIGGER IF EXISTS master_edge_evidence_keeps_edge_covered ON master_edge_evidence;
CREATE CONSTRAINT TRIGGER master_edge_evidence_keeps_edge_covered
  AFTER DELETE OR UPDATE OF master_edge_id ON master_edge_evidence
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION connection_map_edge_has_evidence();

-- ---------------------------------------------------------------------------
-- The supported edge-creation path: edge + evidence atomically.
--
-- SECURITY INVOKER (the default, stated here because it matters): as INVOKER,
-- an anon or authenticated caller would hit the no-policy RLS wall. Execute is
-- additionally revoked from them, so only the service role can call it.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION insert_master_edge_with_evidence(p_edge JSONB, p_evidence JSONB)
RETURNS UUID
LANGUAGE plpgsql
SECURITY INVOKER
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
      quoted_sentence, char_offset, ordinal
    )
    VALUES (
      v_edge_id,
      (v_row->>'source_section_id')::UUID,
      (v_row->>'source_document_id')::UUID,
      v_row->>'section_ref',
      v_row->>'quoted_sentence',
      (v_row->>'char_offset')::INT,
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

ALTER TABLE extraction_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE master_edge ENABLE ROW LEVEL SECURITY;
ALTER TABLE master_edge_evidence ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE master_edge IS
  'Candidate and approved connection-map relationships (SPEC §4.4). No edge reaches a '
  'patient without a Phase 2 attestation; Phase 1 only stores candidates.';
COMMENT ON TABLE master_edge_evidence IS
  'Verbatim guideline quotations. A trigger verifies each quote against its section '
  'character for character at insert; exact matching is the feature guarantee.';
COMMENT ON FUNCTION insert_master_edge_with_evidence(JSONB, JSONB) IS
  'The only supported way to create an edge: writes edge + evidence atomically so the '
  'deferred zero-evidence trigger is satisfied. Service role only.';
