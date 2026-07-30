-- Migration: connection_map — the review role may edit wording, not verdicts
-- Date: 2026-08-04
-- Author: Connection map Phase 5 prep (SPEC §5.8, §0 rule 1)
--
-- THE HOLE. sage_review held table-wide UPDATE on master_edge, so the restricted
-- review connection could set status='approved' directly, with no attestation
-- behind it. Found by probing the live boundary rather than reading it: the
-- probe ran the update and it succeeded, leaving a real edge approved and
-- unsigned on sage-dev (restored immediately).
--
-- The application already refuses this, and says why in a comment that is worth
-- repeating because it predicted this exactly:
--
--   "status and rejection_reason are DELIBERATELY ABSENT. They move only through
--    the attest route, which mints a signature in the same call. Allowing a plain
--    PATCH to set status='approved' would let an edge be marked approved with no
--    signature behind it — the publication gate would still catch it, but 'no
--    connection reaches a patient without a physician attestation' should not
--    depend on one downstream check noticing."
--
-- That was true and enforced in exactly one place: EDITABLE_EDGE_FIELDS in the
-- Flask handler. A bug in that handler, a new endpoint, or anything else holding
-- the review connection could still do it. The repo's own rule is that RLS and
-- application checks are defence in depth and the real enforcement is at the
-- database, so the grant is now as narrow as the code always claimed.
--
-- The publication gate DOES catch it ('has no attestation'), and did. Defence in
-- depth worked. It is still the wrong last line to be relying on, because
-- discovering it at publish time tells you an unsigned edge was approved at some
-- unknown earlier point by something you have not identified.
--
-- WHY SIGNING STILL WORKS. connection_map_attest is SECURITY DEFINER, so its
-- UPDATE runs as the function owner, not as sage_review. Narrowing the role's
-- columns does not touch it — which is the same reason the role holds no INSERT
-- on attestation and signing works anyway.
--
-- The column list is exactly EDITABLE_EDGE_FIELDS + ATTESTING_ONLY_EDGE_FIELDS
-- from lib/connection_map/review/api.py. A test compares the two, because they
-- drifting apart is how this reopens.
--
-- Applied to sage-dev only. Prod has never had these tables.

-- Table-wide UPDATE goes away; only these four columns come back. Postgres has
-- no "revoke one column" — the table-level grant must be dropped first or it
-- keeps overriding the narrower one.
REVOKE UPDATE ON master_edge FROM sage_review;

GRANT UPDATE (
  patient_phrasing,             -- §5.4 Reword
  expected_prevalence_low,      -- §5.4 review input
  expected_prevalence_high,
  urgency                       -- §5.4, attesting-only; enforced by role in the API
) ON master_edge TO sage_review;

COMMENT ON TABLE master_edge IS
  'Physician-reviewable connections. sage_review may UPDATE only patient_phrasing, the prevalence band and urgency: status and rejection_reason move solely through connection_map_attest, which mints the signature in the same transaction. INSERT is withheld entirely — an edge may only be created by the service-role RPC that writes its evidence atomically.';
