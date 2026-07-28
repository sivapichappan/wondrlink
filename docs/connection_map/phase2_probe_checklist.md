# Connection map Phase 2 — PHI boundary probe checklist

Run after applying `2026_07_28_connection_map_reviewers.sql` then
`2026_07_28_connection_map_sage_review_role.sql` (that order; the second grants
on the first's tables).

**Why this exists.** §5.8 requires four tests. Three run in pytest
(`tests/test_connection_map_review_boundary.py`): the import-graph rule, the
fail-closed client, and the grant posture as written in the migration. The
fourth — *connect as `sage_review` and assert a permission error on every
patient table* — needs a real Postgres session, which pytest cannot reach from
this repo. It is the probe below, and it is the one that actually proves the
compliance claim. **Phase 2's gate is not met without it.**

Target: sage-dev (`eizhshntrquvqwfsseeh`). Prod at release.

---

## Setup

The SQL editor and the MCP connector both run as `postgres`, which is a member
of `sage_review` (granted by the migration), so `SET LOCAL ROLE sage_review`
works. Run each probe as its own statement — `SET LOCAL` lasts for the
transaction, and batching an expected failure with setup rolls the setup back.

```sql
-- one visible row, so "0 rows" cannot be mistaken for "working"
INSERT INTO concept (slug, domain, display_clinical, cancer_scopes)
VALUES ('probe_visibility', 'symptom', 'probe visibility', ARRAY['breast']);
```

## Probes

| # | Probe | Expected |
|---|---|---|
| 1 | `SET LOCAL ROLE sage_review; SELECT count(*) FROM patient_edge;` | **ERROR** `permission denied for table patient_edge` |
| 2 | same, `patient_edge_event` | **ERROR** permission denied |
| 3 | same, `auth.users` | **ERROR** `permission denied for schema auth` |
| 4 | same, `patient_profiles` (only where it exists) | **ERROR** permission denied |
| 5 | `SET LOCAL ROLE sage_review; SELECT count(*) FROM concept;` | **1** — not 0. A zero here means a grant without a policy (see below) |
| 6 | `SET LOCAL ROLE sage_review; INSERT INTO audit_log (actor_role, action) VALUES ('x','probe');` | **succeeds** |
| 7 | `SET LOCAL ROLE sage_review; UPDATE audit_log SET action='t' WHERE id=<id>;` | **ERROR** permission denied (UPDATE is not granted) |
| 8 | As `postgres`: `UPDATE audit_log SET action='t' WHERE id=<id>;` | **ERROR** `audit_log is append-only (UPDATE rejected)` — the trigger binds even a role that bypasses RLS (acceptance #25) |
| 9 | As `postgres`: `DELETE FROM audit_log WHERE id=<id>;` | **ERROR** append-only (DELETE rejected) |
| 10 | `INSERT INTO reviewer (...) role='reviewer_attesting', credential='RN'` | **ERROR** `reviewer_attesting_is_physician_check` |
| 11 | `INSERT INTO reviewer (...) status='active'` with null `activated_at` | **ERROR** `reviewer_active_has_timestamp_check` |
| 12 | `INSERT INTO reviewer_assignment (... tiers=ARRAY['A','Z'])` | **ERROR** `reviewer_assignment_tiers_check` |
| 13 | Privilege matrix (query below) | patient tables all false; `DELETE` false everywhere; `master_edge` insert false, update true; `audit_log` update false |
| 14 | Role attributes (query below) | no RLS bypass, no login, `authenticator` can switch in, no `auth` schema, cannot execute the edge RPC |

### Probe 13 — privilege matrix

```sql
SELECT t.tbl,
       has_table_privilege('sage_review', t.tbl, 'SELECT') AS can_select,
       has_table_privilege('sage_review', t.tbl, 'INSERT') AS can_insert,
       has_table_privilege('sage_review', t.tbl, 'UPDATE') AS can_update,
       has_table_privilege('sage_review', t.tbl, 'DELETE') AS can_delete
  FROM unnest(ARRAY['patient_edge','patient_edge_event',
                    'concept','source_document','source_section','extraction_run',
                    'master_edge','master_edge_evidence','master_map_version',
                    'reviewer','reviewer_assignment','audit_log']) AS t(tbl)
 ORDER BY can_select, t.tbl;
```

### Probe 14 — role attributes

```sql
SELECT has_function_privilege('sage_review',
         'insert_master_edge_with_evidence(jsonb, jsonb)', 'EXECUTE') AS can_call_edge_rpc,
       (SELECT rolbypassrls FROM pg_roles WHERE rolname='sage_review')  AS bypasses_rls,
       (SELECT rolcanlogin  FROM pg_roles WHERE rolname='sage_review')  AS can_login,
       pg_has_role('authenticator','sage_review','MEMBER')              AS postgrest_can_switch_into_it,
       has_schema_privilege('sage_review','auth','USAGE')               AS can_touch_auth_schema;
-- expect: false, false, false, true, false
```

## The failure mode probe 5 exists for

These tables have RLS enabled and `sage_review` does **not** bypass it. A table
granted **without** a matching policy returns **zero rows silently** — no
error. The review queue would simply look empty, and the cause would look like
a bug anywhere but here. Every readable table therefore needs a grant **and** a
policy; the migration derives both from one list so they cannot drift, and
`test_every_granted_table_also_gets_a_policy` guards it.

## Cleanup

```sql
DELETE FROM concept WHERE slug = 'probe_visibility';
DELETE FROM reviewer WHERE email LIKE 'probe.%@example.invalid';
```

`audit_log` probe rows **cannot be deleted** — that is the append-only
guarantee working. Expect them to remain.

---

## Run log

**2026-07-28, sage-dev — ALL PROBES PASS.** Verified before and after the
migrations were written: `permission denied for table patient_edge` /
`patient_edge_event`, `permission denied for schema auth`, concept visible with
1 row, audit insert allowed, audit update denied by grant AND by trigger even
as `postgres`, all three reviewer constraints firing, privilege matrix exactly
as intended, role attributes exactly as intended.

**Not yet proven, and honest about it:** probe 4 and the reviewer/patient
mutual-exclusion triggers could not run, because `patient_profiles` does not
exist on unseeded sage-dev. The migration attaches that trigger conditionally
and must be **re-run after sage-dev bring-up, or verified on prod at release**,
before acceptance #5 can be called proven. One `audit_log` row from probe 6
remains on sage-dev by design.
