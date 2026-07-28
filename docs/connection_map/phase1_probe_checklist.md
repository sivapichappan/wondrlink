# Connection map Phase 1 — database enforcement probe checklist

Run this after applying the five `2026_07_28_connection_map_*.sql` migrations,
via the Supabase MCP connector (`execute_sql`) or the dashboard SQL editor.

**Why this exists.** `tests/test_connection_map_migrations.py` asserts the SQL
still *contains* each constraint, but pytest cannot reach Postgres from this
repo (there is no driver and no DB password). These probes are the other half:
they prove the constraints actually *fire*. Phase 1's gate is not met until
every expectation below is observed.

Target: **sage-dev** (`eizhshntrquvqwfsseeh`). These tables depend only on
`auth.users`, so sage-dev's unseeded state does not block them. Prod waits for
the normal release flow.

Run probes **one statement at a time**. The zero-evidence triggers are
`DEFERRABLE INITIALLY DEFERRED` and therefore fire at COMMIT, so batching an
expected failure together with its setup would roll the setup back too.

---

## Setup

```sql
-- Two concepts, one document, one section with known text, one run.
INSERT INTO concept (slug, domain, display_clinical, cancer_scopes)
VALUES ('probe_joint_pain', 'symptom', 'probe joint pain', ARRAY['breast']),
       ('probe_ai', 'treatment', 'probe aromatase inhibitor', ARRAY['breast']);

INSERT INTO source_document (title, publisher, scope, cancer, file_path, content_sha256)
VALUES ('PROBE DOC', 'probe', 'cancer_specific', 'breast', 'data/__probe__.pdf', 'probe');

INSERT INTO source_section (document_id, section_ref, ordinal, heading, text,
                            char_start, char_end, page_start, page_end)
SELECT id, 's0000-probe', 0, 'PROBE',
       'Joint pain is common with an aromatase inhibitor.',
       0, 49, 1, 1
  FROM source_document WHERE file_path = 'data/__probe__.pdf';

INSERT INTO extraction_run (cancer, pass_number, model, prompt_id)
VALUES ('breast', 1, 'probe', 'probe');
```

`text` above is 49 characters; the offset of `'aromatase inhibitor'` inside it
is **29** (0-based). Confirm before probing:

```sql
SELECT char_length(text) AS len,
       strpos(text, 'aromatase inhibitor') - 1 AS zero_based_offset
  FROM source_section WHERE section_ref = 's0000-probe';
-- expect: len = 49, zero_based_offset = 29
```

---

## Probes

Each row states what to run and what MUST happen. An unexpected success is a
failed gate, not a curiosity.

| # | Probe | Expected |
|---|---|---|
| 1 | Bare `INSERT INTO master_edge (...)` with no evidence | **ERROR** at commit: `master_edge ... has no evidence` |
| 2 | `SELECT insert_master_edge_with_evidence(...)` with quote `'aromatase inhibitor'` at offset `29` | **succeeds**, returns an edge uuid |
| 3 | Same RPC, offset `28` (off by one) | **ERROR**: `quoted_sentence does not match section text at offset 28` |
| 4 | Same RPC, quote `'Aromatase inhibitor'` (case changed) at offset 29 | **ERROR**: no match |
| 5 | Same RPC, quote `'aromatase  inhibitor'` (double space) | **ERROR**: no match |
| 6 | Same RPC with `source_document_id` set to a different document | **ERROR**: `evidence document does not match its section document` |
| 7 | Same RPC with `section_ref` = `'wrong-ref'` | **ERROR**: `evidence section_ref does not match its section` |
| 8 | Repeat probe 2 (same src, dst, relationship) | **ERROR**: unique violation on `master_edge_triple_key` |
| 9 | RPC with `tier` = `'C'` | **ERROR**: check violation (`tier`) |
| 10 | RPC with empty evidence array `'[]'::jsonb` | **ERROR**: `at least one evidence row is required` |
| 11 | `UPDATE master_edge SET status='rejected'` (reason still NULL) | **ERROR**: `master_edge_rejected_needs_reason_check` |
| 12 | `UPDATE master_edge SET status='rejected', rejection_reason='too_general'` | **succeeds** |
| 13 | `UPDATE master_edge SET status='approved'` (reason still set) | **ERROR**: same check, the other direction |
| 14 | `DELETE FROM master_edge_evidence WHERE master_edge_id = <edge>` (edge survives) | **ERROR** at commit: has no evidence |
| 15 | `DELETE FROM source_section WHERE id = <cited section>` | **ERROR**: FK `ON DELETE RESTRICT` from evidence |
| 16 | `INSERT INTO master_edge_evidence` directly for probe 2's edge, quote `'Joint pain'` at offset `0`, **`ordinal = 1`** | **succeeds** (adding evidence never needs the RPC) |
| 17 | `UPDATE master_edge_evidence SET quoted_sentence='nonsense'` | **ERROR**: verify trigger |
| 18 | Insert `master_map_version` with `status='published'`, `frozen_hash` NULL | **ERROR**: `master_map_version_published_fields_check` |
| 19 | Insert a draft `master_map_version`, then a `patient_edge` for a sage-dev test user, then a `patient_edge_event`; `UPDATE patient_edge_event SET actor='x'` | **ERROR**: `patient_edge_event is append-only` |
| 20 | `DELETE FROM patient_edge_event WHERE id = <id>` | **succeeds** — right-to-delete carve-out |
| 21 | `INSERT INTO patient_edge (... alpha 0 ...)` | **ERROR**: check violation (`alpha > 0`) |
| 22 | Insert a second `patient_edge` with the same `(patient_id, master_edge_id)` | **ERROR**: `patient_edge_patient_master_key` |
| 23 | `DELETE FROM master_edge WHERE id = <edge with a patient_edge>` | **ERROR**: FK RESTRICT from `patient_edge` |
| 24 | `INSERT INTO source_document` with `scope='general_survivorship'` and a non-null `cancer` | **ERROR**: `source_document_scope_cancer_check` |
| 25 | `INSERT INTO source_section` with `char_end - char_start <> char_length(text)` | **ERROR**: `source_section_span_check` |
| 26 | `INSERT INTO master_edge` (via RPC) with `src_concept_id = dst_concept_id` | **ERROR**: `master_edge_no_self_loop_check` |
| 27 | `INSERT INTO master_edge` (via RPC) with `candidate_origin='literature_scan'` and NULL `extraction_run_id` | **ERROR**: `master_edge_scan_run_check` |

`ordinal` is `INT NOT NULL DEFAULT 0` under `UNIQUE (master_edge_id, ordinal)`,
and only the RPC auto-assigns it. Probe 2 already used ordinal 0 for that edge,
so probe 16 must pass an explicit `ordinal = 1` or it collides.

### Probe 2 template

```sql
SELECT insert_master_edge_with_evidence(
  jsonb_build_object(
    'src_concept_id', (SELECT id FROM concept WHERE slug = 'probe_joint_pain'),
    'dst_concept_id', (SELECT id FROM concept WHERE slug = 'probe_ai'),
    'relationship',   'side_effect_of',
    'tier',           'A',
    'candidate_origin', 'literature_scan',
    'extraction_run_id', (SELECT id FROM extraction_run WHERE model = 'probe'),
    'extraction_pass', 1
  ),
  jsonb_build_array(jsonb_build_object(
    'source_section_id',  (SELECT id FROM source_section WHERE section_ref = 's0000-probe'),
    'source_document_id', (SELECT id FROM source_document WHERE file_path = 'data/__probe__.pdf'),
    'section_ref',        's0000-probe',
    'quoted_sentence',    'aromatase inhibitor',
    'char_offset',        29,
    'ordinal',            0
  ))
);
```

### Function hardening probe (29)

```sql
SELECT proname, proconfig
  FROM pg_proc
 WHERE proname IN ('connection_map_verify_evidence','connection_map_edge_has_evidence',
                   'insert_master_edge_with_evidence','connection_map_block_update');
-- expect every row: proconfig = {"search_path=public, pg_temp"}
```

A mutable `search_path` would let a caller resolve the trigger's unqualified
`source_section` lookup to a decoy table, so a fabricated quotation could pass
verification. `pg_temp` last stops a temp table shadowing a real one.

### Execute-permission probe (28)

Not reachable from the SQL editor, which runs as a superuser. Check the grant
directly instead:

```sql
SELECT has_function_privilege('anon',
         'insert_master_edge_with_evidence(jsonb, jsonb)', 'EXECUTE')        AS anon_can,
       has_function_privilege('authenticated',
         'insert_master_edge_with_evidence(jsonb, jsonb)', 'EXECUTE')        AS authed_can,
       has_function_privilege('service_role',
         'insert_master_edge_with_evidence(jsonb, jsonb)', 'EXECUTE')        AS service_can;
-- expect: false, false, true
```

---

## Cleanup

Order matters (FKs are RESTRICT on purpose).

```sql
DELETE FROM patient_edge_event WHERE actor LIKE 'probe%';
DELETE FROM patient_edge WHERE master_edge_id IN (
  SELECT id FROM master_edge WHERE src_concept_id IN (
    SELECT id FROM concept WHERE slug LIKE 'probe_%'));
DELETE FROM master_map_version WHERE cancer = 'breast' AND governance_note = 'probe';
DELETE FROM master_edge WHERE src_concept_id IN (
  SELECT id FROM concept WHERE slug LIKE 'probe_%');   -- cascades evidence
DELETE FROM extraction_run WHERE model = 'probe';
DELETE FROM source_document WHERE file_path = 'data/__probe__.pdf';  -- cascades sections
DELETE FROM concept WHERE slug LIKE 'probe_%';
```

Then confirm nothing is left:

```sql
SELECT (SELECT COUNT(*) FROM concept WHERE slug LIKE 'probe_%')            AS concepts,
       (SELECT COUNT(*) FROM source_document WHERE file_path LIKE '%__probe__%') AS docs,
       (SELECT COUNT(*) FROM extraction_run WHERE model = 'probe')         AS runs;
-- expect: 0, 0, 0
```

Finally run the Supabase advisors (security) and confirm no new findings
against the connection-map tables.

---

## Recording the result

Phase 1's gate is "migrations clean": all five migrations applied, every probe
above behaving as stated, and `python3 -m pytest tests/` green. Note the date
and the project the probes ran against in `HANDOFF.md` when done — a probe run
against sage-dev says nothing about prod until the migrations are applied
there too.

### Run log

**2026-07-28, sage-dev (`eizhshntrquvqwfsseeh`) — ALL PROBES PASS.** All eight
tables created; every expected failure failed with the expected message and
every expected success succeeded; probe rows cleaned to zero and the throwaway
auth user removed. Two defects were found and fixed during this run:

1. `master_edge_rejection_reason_check` as an explicit constraint name collided
   with the name Postgres auto-generates for the inline `rejection_reason`
   CHECK, so `CREATE TABLE master_edge` failed outright. Renamed to
   `master_edge_rejected_needs_reason_check`.
2. The Supabase linter flagged all four functions as having a mutable
   `search_path` (WARN). Pinned to `public, pg_temp`.

Both are now locked by static tests. Remaining advisor output is INFO-level
`rls_enabled_no_policy` on the seven master-side tables, which is the intended
deny-all posture. **Prod has NOT been touched.**
