-- Migration: connection_map — verbatim source corpus (documents + sections)
-- Date: 2026-07-28
-- Author: Connection map Phase 1 (SPEC-connection-map.md §4.2, PLAN.md)
--
-- WHY A SECOND CORPUS STORE EXISTS. The RAG store (pdf_documents/pdf_chunks)
-- cannot back this feature: lib/pdf_utils.py strips every line, drops blank
-- lines, concatenates pages without boundaries, overlaps chunks ~20%, and
-- discards the section label before insert. The spec's core guarantee is that
-- every citation matches its source CHARACTER FOR CHARACTER (§4.4, §6.1), so
-- the text a citation is checked against has to be stored unmodified. These
-- two tables do that and nothing else. The RAG pipeline is untouched.
--
-- source_section.text is a verbatim slice of the document's canonical text
-- (pdfplumber page text joined with \f, no normalization of any kind).
-- Sections partition that text exactly: concatenating them in ordinal order
-- reproduces the document byte for byte. char_start/char_end are 0-based
-- Unicode code-point offsets into the canonical text, which is what makes
-- Python slicing and Postgres substr() agree (see the evidence trigger in
-- 2026_07_28_connection_map_edges.sql).
--
-- Not patient data: RLS enabled, no policies (service role reaches it).

CREATE TABLE IF NOT EXISTS source_document (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           TEXT NOT NULL,
  publisher       TEXT,
  edition         TEXT,
  scope           TEXT NOT NULL CHECK (scope IN ('cancer_specific','general_survivorship')),
  cancer          TEXT,
  -- A cancer-specific document names its cancer; a general survivorship one
  -- must not (§4.2 splits the corpus on exactly this distinction, and the
  -- review workspace labels each quotation with its scope).
  CONSTRAINT source_document_scope_cancer_check
    CHECK ((scope = 'cancer_specific') = (cancer IS NOT NULL)),
  file_path       TEXT NOT NULL UNIQUE,
  content_sha256  TEXT,          -- of the canonical text; drives skip-if-unchanged re-ingest
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS source_document_scope_idx ON source_document (scope, cancer);

CREATE TABLE IF NOT EXISTS source_section (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id  UUID NOT NULL REFERENCES source_document(id) ON DELETE CASCADE,
  section_ref  TEXT NOT NULL,
  ordinal      INT NOT NULL CHECK (ordinal >= 0),
  heading      TEXT,                       -- verbatim heading line, display only
  text         TEXT NOT NULL,              -- VERBATIM slice; never normalized
  char_start   INT NOT NULL CHECK (char_start >= 0),
  char_end     INT NOT NULL CHECK (char_end > char_start),
  page_start   INT,
  page_end     INT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT source_section_span_check CHECK (char_end - char_start = char_length(text)),
  CONSTRAINT source_section_doc_ordinal_key UNIQUE (document_id, ordinal),
  CONSTRAINT source_section_doc_ref_key UNIQUE (document_id, section_ref)
);

CREATE INDEX IF NOT EXISTS source_section_document_idx ON source_section (document_id, ordinal);

ALTER TABLE source_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_section ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE source_document IS
  'Connection-map source corpus (SPEC §4.2). Separate from pdf_documents: this side '
  'preserves text verbatim so citations can be verified character for character.';
COMMENT ON TABLE source_section IS
  'Verbatim section slices. Sections partition the document canonical text exactly; '
  'char offsets are 0-based code points so Python slicing and Postgres substr() agree.';
