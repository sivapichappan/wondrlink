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
