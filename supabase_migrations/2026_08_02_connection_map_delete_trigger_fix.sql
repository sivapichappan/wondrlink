-- Migration: connection_map — a DELETE on master_edge silently did nothing
-- Date: 2026-08-02
-- Author: Connection map Phase 4 (fixes a Phase 3 defect)
--
-- THE BUG. connection_map_block_published_edge_edit() guards master_edge with
-- BEFORE UPDATE OR DELETE, and ended with `RETURN NEW`. In a DELETE trigger NEW
-- is NULL, and a BEFORE ... FOR EACH ROW trigger that returns NULL CANCELS the
-- operation. So every DELETE on master_edge was silently discarded: PostgREST
-- returned 204, the row stayed, and nothing anywhere reported a problem.
--
-- Found while removing five candidate edges built on leftover Phase 3 fixture
-- concepts. The deletes "succeeded" five times and the rows were still there.
--
-- Its sibling trigger on master_edge_evidence already did this correctly with
-- `RETURN COALESCE(NEW, OLD)`, which is what a trigger covering both operations
-- has to return. The two were written in the same commit; only one was right.
--
-- WHY IT MATTERED MORE THAN IT LOOKED. The intent was narrow — freeze edges that
-- are part of a PUBLISHED version — and that half worked, because it RAISEs
-- before reaching the return. The damage was to every other edge: an
-- unpublished candidate could not be deleted at all, and the failure was
-- invisible, which is worse than a refusal. A guard that silently swallows the
-- operation it was meant to allow is indistinguishable from data loss in the
-- other direction, and nothing in the Phase 3 probe checklist covered
-- "delete a NON-published edge and confirm it is gone".
--
-- Applied to sage-dev only. Prod has never had these tables.

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
  -- COALESCE, not NEW: on DELETE, NEW is NULL and returning it would cancel the
  -- delete instead of allowing it.
  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION connection_map_block_published_edge_edit() IS
  'Freezes edges belonging to a published version. Returns COALESCE(NEW, OLD) because NEW is NULL on DELETE and returning NULL from a BEFORE row trigger cancels the operation silently.';
