-- Migration: connection_map — the sage_review restricted database account
-- Date: 2026-07-28
-- Author: Connection map Phase 2 (SPEC-connection-map.md §5.8)
-- Apply AFTER 2026_07_28_connection_map_reviewers.sql (grants on its tables).
--
-- THIS FILE IS THE PHI BOUNDARY. Everything else about reviewer access is
-- convenience; this is the part that makes "a reviewer provably cannot reach
-- patient data" a fact about the database rather than a claim about our code.
--
-- HOW IT WORKS ON THIS STACK. The spec (§5.8) describes a dedicated connection
-- pool. This app has no Postgres driver and no connection string — everything
-- goes through PostgREST — so the same guarantee is obtained the way PostgREST
-- supports natively: a Postgres role, granted to `authenticator`, selected per
-- request by the `role` claim in a JWT. Review handlers use a client holding a
-- sage_review token; PostgREST executes their queries AS sage_review, and a
-- query against a patient table fails with "permission denied for table" at
-- the database. Verified empirically on sage-dev before this was written.
--
-- TWO PROPERTIES THIS ROLE MUST KEEP, both easy to lose by accident:
--
--   1. NO BYPASSRLS. service_role has it, which is why the app sees
--      everything. sage_review must never be granted it.
--   2. A GRANT ALONE IS NOT ACCESS, AND ITS ABSENCE IS NOT AN ERROR. These
--      tables have RLS enabled, and sage_review does not bypass it, so a table
--      granted WITHOUT a matching policy returns ZERO ROWS SILENTLY rather
--      than raising. A review queue would simply look empty. Every readable
--      table therefore needs BOTH a grant and a policy, and
--      tests/test_connection_map_review_boundary.py fails on any mismatch.
--
-- PRIVILEGES ARE TIGHTER THAN §5.8's BLANKET "SELECT, INSERT, UPDATE", by
-- intent. Each narrowing is noted at its table below. Nothing anywhere gets
-- DELETE.

-- ---------------------------------------------------------------------------
-- The role
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sage_review') THEN
    CREATE ROLE sage_review NOLOGIN;
  END IF;
END $$;

-- NOLOGIN + NOBYPASSRLS, restated so a later ALTER cannot drift silently.
ALTER ROLE sage_review NOLOGIN NOBYPASSRLS;

-- Lets PostgREST switch into this role from a JWT `role` claim.
GRANT sage_review TO authenticator;
-- Lets an operator SET ROLE sage_review to run the boundary probes.
GRANT sage_review TO postgres;

GRANT USAGE ON SCHEMA public TO sage_review;

-- ---------------------------------------------------------------------------
-- Review-side privileges + the policies that make them effective.
--
-- The posture lives in one literal so it reads as a single table of intent and
-- so 30-odd near-identical statements cannot drift apart by copy-paste.
--
--   concept              SELECT INSERT UPDATE  physicians may add concepts and
--                                              author display_patient (D3, §5.4)
--   source_document      SELECT                reviewers read sources, never ingest
--   source_section       SELECT                needed to show a quote IN CONTEXT
--                                              (§5.4); not in §5.8's list only
--                                              because that list predates the
--                                              verbatim section store
--   extraction_run       SELECT                provenance display only
--   master_edge          SELECT UPDATE         approve / reject / reword.
--                                              INSERT WITHHELD: an edge may only
--                                              be created by the service-role RPC
--                                              that writes its evidence atomically
--   master_edge_evidence SELECT                read-only. Editing evidence must
--                                              stay a service-role operation:
--                                              it voids attestations (§5.6) and
--                                              is verbatim-verified
--   master_map_version   SELECT INSERT UPDATE  drafting and publication (Phase 3)
--   reviewer             SELECT                see below
--   reviewer_assignment  SELECT                see below
--   audit_log            SELECT INSERT         append-only; UPDATE withheld so
--                                              the grant agrees with the trigger
--
-- WHY reviewer AND reviewer_assignment ARE READ-ONLY HERE, against §5.8's
-- blanket INSERT/UPDATE. Account provisioning is not review work; it is a
-- privileged server operation, and running it as sage_review is actively
-- harmful in two ways:
--
--   1. It breaks. Writing reviewer.auth_user_id fires the mutual-exclusion
--      trigger, which reads patient_profiles — a table sage_review holds no
--      privilege on — so §5.2 activation would fail every time with
--      "permission denied for table patient_profiles".
--   2. It leaks. Were that permission granted, the trigger becomes a patient
--      existence oracle: submit a candidate UUID as auth_user_id and the
--      distinct error message confirms whether that person is a patient. That
--      is patient data escaping through an error string, which is exactly what
--      §5.8 exists to prevent.
--
-- So provisioning runs through the service-role path behind an admin endpoint,
-- and the review client only ever reads these two tables.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  spec   TEXT[][] := ARRAY[
    ['concept',              'SELECT,INSERT,UPDATE'],
    ['source_document',      'SELECT'],
    ['source_section',       'SELECT'],
    ['extraction_run',       'SELECT'],
    ['master_edge',          'SELECT,UPDATE'],
    ['master_edge_evidence', 'SELECT'],
    ['master_map_version',   'SELECT,INSERT,UPDATE'],
    ['reviewer',             'SELECT'],
    ['reviewer_assignment',  'SELECT'],
    ['audit_log',            'SELECT,INSERT']
  ];
  tbl    TEXT;
  privs  TEXT;
  cmd    TEXT;
  i      INT;
BEGIN
  FOR i IN 1 .. array_length(spec, 1) LOOP
    tbl   := spec[i][1];
    privs := spec[i][2];

    IF to_regclass('public.' || tbl) IS NULL THEN
      RAISE EXCEPTION 'connection_map: expected table % to exist before granting', tbl;
    END IF;

    EXECUTE format('GRANT %s ON %I TO sage_review', privs, tbl);

    -- One policy per granted command. Without these the grants are inert and
    -- every read silently returns nothing.
    FOREACH cmd IN ARRAY string_to_array(privs, ',') LOOP
      EXECUTE format('DROP POLICY IF EXISTS %I ON %I',
                     tbl || '_sage_review_' || lower(cmd), tbl);
      IF cmd = 'INSERT' THEN
        EXECUTE format('CREATE POLICY %I ON %I FOR INSERT TO sage_review WITH CHECK (true)',
                       tbl || '_sage_review_insert', tbl);
      ELSIF cmd = 'UPDATE' THEN
        EXECUTE format('CREATE POLICY %I ON %I FOR UPDATE TO sage_review USING (true) WITH CHECK (true)',
                       tbl || '_sage_review_update', tbl);
      ELSE
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO sage_review USING (true)',
                       tbl || '_sage_review_select', tbl);
      END IF;
    END LOOP;
  END LOOP;
END $$;

-- audit_log is BIGSERIAL; INSERT needs its sequence.
GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO sage_review;

-- Withdraw write access this migration granted in an earlier revision, so
-- re-applying converges instead of leaving the wider grant in place. Policies
-- go too: a leftover INSERT policy plus a re-added grant would silently
-- restore the oracle described above.
REVOKE INSERT, UPDATE ON reviewer FROM sage_review;
REVOKE INSERT, UPDATE ON reviewer_assignment FROM sage_review;
DROP POLICY IF EXISTS reviewer_sage_review_insert ON reviewer;
DROP POLICY IF EXISTS reviewer_sage_review_update ON reviewer;
DROP POLICY IF EXISTS reviewer_assignment_sage_review_insert ON reviewer_assignment;
DROP POLICY IF EXISTS reviewer_assignment_sage_review_update ON reviewer_assignment;

-- ---------------------------------------------------------------------------
-- Patient tables: explicitly stripped.
--
-- A brand-new role starts with no privileges, so these REVOKEs are belt and
-- braces. They are written out anyway because this list IS the compliance
-- argument, and a reviewer of this migration should be able to read what is
-- excluded without cross-referencing the rest of the schema.
--
-- Guarded on existence: the connection-map tables are present everywhere, but
-- the older patient tables do not exist on an unseeded dev project. Re-run
-- this migration after sage-dev bring-up.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  patient_tables TEXT[] := ARRAY[
    -- connection map, patient side
    'patient_edge', 'patient_edge_event',
    -- belief store, chat, and everything else patient-identifiable
    'patient_profiles', 'accounts', 'conversations', 'messages', 'chat_messages',
    'chat_feedback', 'patient_events', 'safety_classifications', 'screening_scores',
    'glossary_terms', 'user_acknowledgements', 'consent_withdrawals', 'rate_limits',
    -- dormant learning loop: de-identified, but §0 rule 2 keeps it untouchable
    'pattern_records'
  ];
  tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY patient_tables LOOP
    IF to_regclass('public.' || tbl) IS NOT NULL THEN
      EXECUTE format('REVOKE ALL PRIVILEGES ON %I FROM sage_review', tbl);
    END IF;
  END LOOP;
END $$;

-- Nothing in auth is reachable either.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA auth FROM sage_review;
REVOKE ALL PRIVILEGES ON SCHEMA auth FROM sage_review;

COMMENT ON ROLE sage_review IS
  'Restricted PostgREST role for connection-map review handlers (SPEC 5.8). No BYPASSRLS, no DELETE anywhere, zero privileges on patient tables. Selected via the role claim in a review JWT.';
