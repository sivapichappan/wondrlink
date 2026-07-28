# Supabase migrations + the dev-first flow

Two projects (implementation guidelines, 2026-07-22):

| Project | Ref | Role |
|---|---|---|
| WondrChat (prod) | `kgcelxfhmhymutyrorpw` | LIVE with pilot users. Migrations land here at release. |
| sage-dev | `eizhshntrquvqwfsseeh` | Day-to-day development target. Migrations land here FIRST. |

## Applying migrations
Via the Supabase MCP connector (`apply_migration`) or the dashboard SQL editor,
in filename order. Never manual table edits in the prod dashboard.

## sage-dev bring-up (one-time, still to do)
The files in this directory are INCREMENTAL — the base tables
(patient_profiles, conversations, messages, user_acknowledgements,
screening_scores, chat_messages, chat_feedback, pdf_documents, pdf_chunks,
document_metadata, rate_limits, plus the match_chunks RPC and the pgvector
extension) were created in the prod dashboard and have no CREATE files here.
To seed dev:
1. `supabase db dump --db-url postgresql://postgres:<PROD_DB_PASSWORD>@db.kgcelxfhmhymutyrorpw.supabase.co:5432/postgres --schema-only -f schema.sql`
   (needs the prod database password from the dashboard)
2. Apply `schema.sql` to sage-dev (SQL editor or psql), which carries every
   table + policy + function, then confirm the files here are all reflected.
3. Seed the colorectal corpus only: run `scripts/generate_embeddings.py` /
   the chunk-seeding script against dev env vars (scoped seed — full
   10-cancer ingestion is hours and not needed for dev parity).
4. Dashboard: enable the Phone provider + TEST phone numbers on sage-dev
   (same as prod), e.g. `+15550001111 = 123456`.
5. `.env.development` with the sage-dev URL + keys; mobile dev builds point
   at it via `EXPO_PUBLIC_*`.

## Table inventory & RLS status
See `docs/sage-implementation-guidelines-notes.md` and the individual
migration files. New user-owned tables MUST ship with RLS enabled + an
own-rows policy, and be added to `delete_all_user_data` in
`lib/supabase_storage.py` in the same change.

## Connection map (2026_07_28_connection_map_*.sql)
Five files, apply in filename order: concepts → corpus → edges →
map_versions → patient. They depend only on `auth.users`, so they apply to
an unseeded sage-dev without the bring-up above.

These are the only migrations in this repo that create plpgsql functions and
triggers. That is deliberate: the backend connects as the service role, which
bypasses RLS, so a trigger is the only thing that can actually enforce the
citation invariants (SPEC-connection-map.md §16 requires database-level
enforcement). `master_edge` rows must be created through the
`insert_master_edge_with_evidence` RPC — a bare insert fails at COMMIT.

After applying, run `docs/connection_map/phase1_probe_checklist.md`: static
tests assert the SQL contains each constraint, the probes prove they fire.
