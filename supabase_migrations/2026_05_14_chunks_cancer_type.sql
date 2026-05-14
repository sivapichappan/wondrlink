-- Phase 1 of the multi-cancer expansion — pdf_chunks metadata.
--
-- Adds per-chunk metadata so retrieval can hard-filter to
-- {selected_cancer ∪ 'general'} via lib/pdf_utils.py hybrid_search.
--
-- cancer_types is an ARRAY because a single chunk can legitimately
-- belong to multiple cancers (e.g. distress management is tagged
-- ['general']; a Lynch-syndrome page might be tagged
-- ['colorectal','uterine']).
--
-- After this migration is applied, run:
--   python scripts/backfill_chunk_metadata.py --apply
-- to backfill the existing corpus (single-bulk update — idempotent).

ALTER TABLE pdf_chunks
  ADD COLUMN IF NOT EXISTS cancer_types TEXT[] DEFAULT ARRAY['general']::TEXT[],
  ADD COLUMN IF NOT EXISTS doc_type TEXT,
  ADD COLUMN IF NOT EXISTS audience TEXT,
  ADD COLUMN IF NOT EXISTS guideline_org TEXT;

CREATE INDEX IF NOT EXISTS pdf_chunks_cancer_types_idx
  ON pdf_chunks USING GIN (cancer_types);
