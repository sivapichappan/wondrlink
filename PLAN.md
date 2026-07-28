# Connection Map — recon report + Phase 1 plan

_Approved 2026-07-27. Spec: `SPEC-connection-map.md` (repo root). This file covers
PHASE 1 ONLY; later phases get their own plan sections when their turn comes._

## Context

Implementing SPEC-connection-map.md v3: a physician-attested, literature-cited knowledge
graph (breast pilot) layered onto Sage. Phase 1 only: schema, migrations, concept seed,
corpus ingest. Gate: migrations clean. Everything else (reviewer roles, extraction,
runtime, consumers) is later phases.

Headline recon finding: a per-patient connection graph ALREADY EXISTS (`lib/modeler.py`,
edges in `patient_profiles.raw_profile['connections']`, statuses hypothesis/corroborated/
refuted) and is already consumed by chat prompt, question policy, and trial ranking. The
spec's feature is the missing physician-attested master layer; every integration seam the
spec needs already exists and takes `None` for byte-identical fallback. New tables must
not collide with that naming (nothing called just "connections").

## §1 integration-point map (verified file paths)

| Spec system | Where it lives | Registration seam |
|---|---|---|
| Belief store | `lib/patient_model.py` (beliefs in `patient_profiles.raw_profile`; statuses: provisional / confirmed / invalidated; pending is a sibling queue) | Read via `get_belief()`; no confirmed-facts reader exists — instantiator writes its own filter on `status=="confirmed"`. Change hook = consume `patient_events` stream (kinds `belief_add/update/confirm/...`), exactly how the Modeler attaches |
| Modeler | `lib/modeler.py` (`run_for_user` :848); triggers: Vercel cron `GET /api/modeler/cron` (api/index.py:615), end-of-chat `POST /api/modeler/run` (:589) | No task registry — new modeler tasks = separate pass modeled on `run_for_user` + own `vercel.json` cron entry (non-invasive), or edits to `parse_modeler_output` (invasive; avoid) |
| Question policy | `lib/question_policy.py` (`select_next_question` :207) | Arbitration is type-agnostic; the seam is the `expectation_candidates` param (Modeler namespaces topics `exp:<id>`; ours become `conn:<edge_id>`). One merge line at api/index.py:1760. Answers: model as pending-confirmation entries → existing `POST /api/confirm_belief` handles them unchanged |
| Safety classifier | `lib/safety_classifier.py` + `lib/safety_rules.py` + `config/safety/*.json` | Urgent-edge routing = data, not code: the local-extensions JSON, or direct `deterministic_match`/`classify_message` calls |
| RAG chat | `POST /api/chat` (api/index.py:1373) → `assemble_prompt` (lib/llm_utils.py:2319) | Exact seam: `connections_summary` kwarg → STEP 6d (:2750), own TOKEN_BUDGET key + `pii_guard_payload` entry; `None` ⇒ byte-identical prompt (precedent test: tests/test_trials_ranking.py:51) |
| Trial matching | `lib/clinical_trials.py` `score_trial_relevance` :1124 | Optional-features precedent: `connections=None` kwarg + section-8 block (:1283); flag-gate at the two call sites (api/index.py:1934, :2490). Boosts only, never hard filters |
| Onboarding | Mobile: `mobile/app/_layout.tsx` RootGate (:40-97) → `(onboarding)/consent.tsx`; backend `api_save_acknowledgement` (api/index.py:864) → `user_acknowledgements` (lib/supabase_storage.py:1162); copy in `shared/disclaimers.ts`, version in `shared/consent-version.ts` + `lib/compliance.py` | Honesty-commitment step (Phase 9) slots between `needs_consent` and `needs_basics` gates; needs a new boolean on `/api/check_acknowledgement`. No `copy_version` concept exists yet — new construction |
| Learning loop | `lib/learning_loop.py` — dormant (`FEATURE_MODEL_IMPROVEMENT` default false + per-user opt-in); nothing imports it | Untouched. Its `_ALLOWED_RECORD_KEYS` already whitelists `connection_strength` — do NOT use it; that key is inside the attorney gate |

## Spec-vs-repo conflicts (spec says "follow the repo and tell me what changes")

1. **No direct Postgres access exists.** All DB I/O is supabase-py PostgREST as
   `service_role` (`lib/supabase_client.py`); no Postgres driver, no connection string,
   no psql from this machine. Consequences: (a) RLS is defense-in-depth ONLY —
   service_role bypasses it — so the spec's DB-level enforcement must be CHECK
   constraints + triggers, which DO bind service_role; (b) §5.8's "dedicated connection
   pool using role `sage_review`" cannot be built as specced — Phase 2 options are a new
   restricted PostgREST client (third key/JWT mapped to a `sage_review` Postgres role)
   or adding a Postgres driver + Supavisor pooler. Decision needed AT PHASE 2, flagged
   now.
2. **No React web frontend.** Web = one vanilla-JS `public/index.html`; mobile = Expo RN
   (expo-router; web build support configured but not deployed). Zero React web code,
   zero role-gated routes, zero JWT-claim reads (backend `verify_token` discards claims).
   The §5.4 review workspace + §5.5 sandbox (Phase 3) need a frontend decision then —
   candidates: role-gated expo-router routes vs. a page in `public/`. Not a Phase 1
   blocker.
3. **`pdf_chunks` cannot back citation checks.** Chunking strips/normalizes/overlaps and
   discards section labels, page numbers, offsets (lib/pdf_utils.py). Phase 1 builds a
   NEW section-preserving store + ingester; existing RAG pipeline untouched.
4. **Migrations layout/house style.** Spec's `connection_map/migrations/` →
   repo's `supabase_migrations/YYYY_MM_DD_*.sql` applied via Supabase MCP/dashboard.
   House style = TEXT+CHECK, not `CREATE TYPE` enums (keep); but zero precedent for
   triggers/functions — the spec's DB-level mandates make that departure deliberate.
5. **No usable staging DB.** `sage-dev` exists, unseeded, blocked on prod DB password;
   today migrations land on PROD first (live pilot users). User decision requested below.
6. **Repo layout.** Spec's top-level `connection_map/` → `lib/connection_map/` (bare
   imports, matches sys.path convention); config → `config/connection_map/*.yaml`
   (ships to Vercel; never .md — blanket `*.md` .vercelignore exclusion). Scripts →
   `scripts/` (local-only, like existing seeders).
7. **Corpus gap.** Breast corpus exists (12 PDFs). "General survivorship" = 7 docs
   (caregiver/stress/sleep themed); no survivorship-care-plan/late-effects guideline —
   §10.3 co-occurrence extraction will underproduce until sources are added (user ops).
8. **Spec-internal inconsistency.** §10.2-10.4 reference 7 concepts absent from §10.1:
   skin changes, numbness near the scar, LVEF decline (a finding, vs the lab LVEF), bone
   mineral density loss (vs the lab), annual gynecologic assessment, arm exercise and
   skin care, sleep routine. Without them several extraction targets are inexpressible
   (pass 1 rejects concepts not in the table). Proposed: seed them marked
   `spec_addition: true` so the reviewer sees them — flagged for approval, not silently
   fixed. (§10.2's separate "hair loss" / "hair thinning" rows need NO new concept: both
   map to §10.1's single "hair loss or thinning".)
9. **Tier C.** §4.4 defines tier enum A|B|C yet says C is "discarded, never queued" —
   nothing may legitimately write C. Proposed deviation: `CHECK (tier IN ('A','B'))`.
10. **`extraction_run` referenced but never defined** — minimal implied-infrastructure
    table designed in Phase 1.
11. **Right-to-delete vs append-only.** Patient tables must join `delete_all_user_data`
    (repo rule); `patient_edge_event`'s append-only trigger therefore blocks UPDATE only,
    allowing DELETE. Phase 2's `attestation`/`audit_log` (non-patient) get hard
    append-only (spec #25).
12. **Auth model.** Reviewers (Phase 2) need email magic-link + roles; today auth is
    phone-OTP/password, no roles anywhere, and `verify_token` is a Supabase round-trip
    that discards JWT claims. Flagged for Phase 2 design.

## Phase 1 plan (schema, migrations, concept seed, corpus ingest — gate: migrations clean)

Nothing here touches chat, question policy, safety, or any patient-facing surface; no
feature flag is needed yet because no runtime code path exists until Phase 7.

### 1. Migrations — 5 files in `supabase_migrations/`, lexical order = dependency order

House idioms throughout: prose header, `CREATE TABLE IF NOT EXISTS`, TEXT+CHECK (no
`CREATE TYPE`), `DROP POLICY/TRIGGER IF EXISTS` before CREATE, `CREATE OR REPLACE
FUNCTION`, named indexes, `COMMENT ON TABLE`, TIMESTAMPTZ DEFAULT NOW(). RLS posture:
master-side tables → RLS enabled with NO policies (deny-all to anon/authed; service_role
bypasses); patient tables → house own-rows SELECT policy. Real enforcement = CHECKs +
triggers (bind service_role too). Headers state that triggers/plpgsql are a deliberate,
spec-mandated departure from house style.

1. **`2026_07_28_connection_map_concepts.sql`** — `concept`: uuid PK, `slug UNIQUE`,
   `domain` CHECK (6 values), `display_clinical NOT NULL`, `display_patient NULL` (null
   until publication), terminology_system/code, `instrument` CHECK (5 values),
   `cancer_scopes TEXT[] DEFAULT '{}'` + GIN index, timestamps.
2. **`2026_07_28_connection_map_corpus.sql`** — `source_document` (title, publisher,
   edition, `scope` CHECK cancer_specific|general_survivorship, `cancer NULL` +
   `CHECK ((scope='cancer_specific') = (cancer IS NOT NULL))`, `file_path UNIQUE`,
   `content_sha256`, ingested_at) + **`source_section`** (the spec-implied store the
   citation trigger reads): document FK CASCADE, `section_ref`, `ordinal`, `heading`,
   `text NOT NULL` (char-for-char verbatim), `char_start/char_end` (offsets into the
   document canonical text), `page_start/page_end`, UNIQUE (document_id, ordinal) and
   (document_id, section_ref).
3. **`2026_07_28_connection_map_edges.sql`** — the core:
   - `extraction_run` (implied infra, minimal): cancer, `pass_number`, model,
     `prompt_id`, started/finished, stats JSONB.
   - `master_edge` per spec §4.4 with: relationship CHECK (6 types), urgency CHECK,
     `tier CHECK (tier IN ('A','B'))` [deviation, see decisions], status CHECK
     (candidate|in_review|approved|rejected), candidate_origin CHECK, prior_alpha
     DEFAULT 2 / prior_beta DEFAULT 1 (both > 0), prevalence bounds CHECK [0,1] and
     low<=high, rejection_reason CHECK (the 8 §13.1 values) +
     `CHECK ((status='rejected') = (rejection_reason IS NOT NULL))` (acceptance #26,
     bidirectional), `CHECK (src <> dst)`, `UNIQUE (src, dst, relationship)`.
   - `master_edge_evidence`: edge FK CASCADE, **`source_section_id` FK RESTRICT**
     (design call: FK the section row directly so the verify trigger does an indexed
     lookup; re-ingesting a cited document fails loudly instead of silently
     invalidating citations), plus denormalized `source_document_id` + `section_ref`
     per spec (trigger cross-checks them), `quoted_sentence NOT NULL`,
     `char_offset >= 0`, `ordinal`, UNIQUE (master_edge_id, ordinal).
   - **Trigger A (verbatim evidence, §4.4 "verified at insert")**: BEFORE INSERT OR
     UPDATE on evidence → RAISE unless
     `substr(section.text, char_offset+1, char_length(quoted_sentence)) = quoted_sentence`
     (exact equality, zero normalization) and document/section_ref cross-check passes.
   - **Trigger B (zero-evidence edge ban, acceptance #13)**: DEFERRABLE INITIALLY
     DEFERRED constraint triggers on `master_edge` (AFTER INSERT) and on evidence
     (AFTER DELETE/UPDATE) → an edge with zero evidence rows cannot survive commit.
     Because PostgREST runs each request in its own transaction, inserts go through a
     plpgsql RPC **`insert_master_edge_with_evidence(p_edge, p_evidence[])`** (edge +
     evidence atomically; precedent: `match_chunks` RPC in lib/vector_search.py:84).
     SECURITY INVOKER + `REVOKE EXECUTE FROM anon, authenticated` — only service_role
     can call it. Raw two-step inserts fail closed at commit.
4. **`2026_07_28_connection_map_map_versions.sql`** — `master_map_version`: cancer,
   version, UNIQUE (cancer, version), status CHECK (draft|published|superseded —
   proposed value set), published_at, `published_by UUID NULL` (Phase 2 adds reviewer
   FK), `edge_ids UUID[]`, frozen_hash, governance_note,
   `CHECK (status <> 'published' OR (published_at IS NOT NULL AND frozen_hash IS NOT NULL))`.
   Full immutability trigger deferred to Phase 3 (the publication gate owns its exact
   carve-outs); the CHECK is the interim guard.
5. **`2026_07_28_connection_map_patient.sql`** — `patient_edge` (patient_id →
   auth.users CASCADE; master_edge/map_version FKs RESTRICT; status CHECK the 5 §4.7
   values; alpha/beta > 0 no defaults — app copies master priors; ask_count;
   UNIQUE (patient_id, master_edge_id); RLS + own-rows SELECT) and
   `patient_edge_event` (BIGSERIAL; patient_edge FK CASCADE; **plus `patient_id`
   column** [flagged addition] so right-to-delete and RLS need no join; event_type
   un-CHECKed until Phase 7 defines the vocabulary; from/to_status CHECKs; payload
   JSONB; **Trigger C: BEFORE UPDATE → RAISE "append-only"; DELETE deliberately
   allowed** — right-to-delete carve-out for patient tables). Same commit edits
   `delete_all_user_data()` (lib/supabase_storage.py:1674) to add both tables — repo
   rule, same change.

### 2. Concept seed

- **`config/connection_map/concepts_breast.yaml`** (ships to Vercel; YAML never .md).
  §10.1 **verbatim**: 5 biomarkers, 8 treatments, 5 procedures, the exact 22 symptoms
  (joint pain, muscle pain, hot flashes, night sweats, fatigue, peripheral neuropathy,
  balance problems, falls, nausea, hair loss or thinning, lymphedema, vaginal dryness,
  painful intercourse, low libido, cognitive complaints, cardiac symptoms, fever,
  vaginal bleeding, leg pain or swelling, arm redness or warmth, weight gain, general
  pain), 5 labs, 8 daily_life — plus the 7 `spec_addition: true` concepts from
  conflict #8. `display_patient: null` everywhere (physician review fills it — plain
  language is the reviewer's Reword job, not ours to invent). ~72 rows.
- **`lib/connection_map/concepts.py`** — enum constants (single source of truth,
  cross-checked against migration SQL by the static test) + `load_concepts` /
  `validate_concepts` (unique slugs, `^[a-z0-9_]+$`, valid domain/instrument,
  display_clinical non-empty, cancer in cancer_scopes, unknown keys rejected).
  Package `lib/connection_map/`, imported bare (`from connection_map...`).
- **`scripts/seed_connection_map_concepts.py`** — modeled on scripts/seed_chunks.py
  (.env, service client, validate-or-abort, `upsert(on_conflict='slug')`, `--check`
  flag, idempotent). Header notes: once physician-curated columns exist (Phase 2+),
  the seeder must stop clobbering them.

### 3. Corpus ingest

- **`config/connection_map/corpus_manifest.yaml`** — 20 documents: the 13
  breast-tagged PDFs on disk (12 `*breast*` + `9671.00.pdf`, ACS breast screening per
  data/_filename_to_metadata.yaml) + the 7 `[general]` docs. Fields per doc: file,
  title, publisher, edition, scope, cancer.
- **Section model (normative, tests encode it):** canonical text =
  `"\f".join(page.extract_text() or "" for page in pages)` — no strip, no blank-line
  removal, no unicode normalization, no fallback extractor (different extraction ⇒
  different offsets; unreadable PDF fails loudly). Sections are pure cut-points at
  line starts: concatenating sections in ordinal order reproduces the canonical text
  byte-for-byte; min-length merges forward, max ~20k chars force-splits at a page
  boundary; `section_ref` = `s{ordinal:04d}[-slug]`; `char_offset` = 0-based code-point
  offset (Python slice ≡ Postgres `substr(text, off+1, len)` — the equivalence the
  verify trigger relies on). NUL byte in extracted text = hard fail (substitution
  would break verbatim semantics).
- **`lib/connection_map/corpus.py`** — pure `sectionize(page_texts)` (heading regexes
  inspired by lib/pdf_utils.py:90-97; text never mutated). pdfplumber stays in the
  script, keeping the lib pure/testable.
- **`scripts/ingest_connection_map_corpus.py`** — per manifest entry: extract →
  sha256 → skip-if-unchanged (`--force` overrides) → sectionize → upsert
  source_document on file_path, delete-and-reinsert sections (seed_chunks.py:157
  pattern; evidence FK RESTRICT aborts re-ingest of a cited doc — deliberate) →
  **post-insert self-verification** (fetch back, assert concatenation equals canonical
  + spot substr probes) → summary. Local-only; never touches pdf_chunks/pdf_documents.

### 4. Tests written FIRST (offline pytest, house per-file style; committed with the code they guard)

| File | Guards |
|---|---|
| `tests/test_connection_map_concepts.py` | Seed YAML: every §10.1 slug present (hardcoded acceptance list), exactly 7 `spec_addition` rows, unique/valid slugs, domains/instruments in enums, breast in scopes; validator rejects synthetic bad inputs |
| `tests/test_connection_map_sectioning.py` | Partition invariant (`''.join == canonical`), slice-exact offsets, offset arithmetic across `\f` page joins + a section spanning a page break, unicode hazards (é, NBSP, en-dash, combining chars), preamble section, determinism, guards never drop characters |
| `tests/test_connection_map_ingest.py` | Manifest validation (missing file, scope/cancer mismatch), sha-skip/`--force`, delete-then-insert call order (mocked client), NUL hard-fail |
| `tests/test_connection_map_migrations.py` | Static SQL asserts (the only DB-enforcement check that can run in pytest): every CHECK/UNIQUE/trigger/RPC named above exists; tier CHECK lacks 'C'; enum lists match `concepts.py` constants; RPC is not SECURITY DEFINER + has the REVOKE; RLS enabled everywhere + own-rows policies on patient tables; `DROP ... IF EXISTS` idempotency; **and** `delete_all_user_data` source contains both patient tables |

### 5. Post-apply probe checklist (real DB enforcement — via Supabase MCP `execute_sql`, committed as `docs/connection_map/phase1_probe_checklist.md`)

On sage-dev after `apply_migration` x5: bare edge insert → fails at commit; RPC with
correct quote → succeeds; off-by-one offset / one-char-different quote / stripped
space → verify-trigger error; mismatched document FK → error; duplicate
(src,dst,rel) → unique violation; rejected-with-null-reason and approved-with-reason →
CHECK violations; tier 'C' → CHECK violation; UPDATE patient_edge_event → append-only
error, DELETE same row → succeeds (right-to-delete proven); deleting an edge's last
evidence → deferred-trigger error; publish with null frozen_hash → CHECK violation.
Cleanup to zero probe rows; `get_advisors` shows no new security findings.

### 6. Commit sequence (small, one concern each)

0. Spec + plan into the repo: `SPEC-connection-map.md` + `PLAN.md` at root (root *.md
   is Vercel-excluded — irrelevant, not runtime files).
1. Concept vocabulary: seed YAML + `lib/connection_map/` validator + its test.
2. Migrations 1–4 + static-SQL test.
3. Migration 5 + `delete_all_user_data` parity edit + test extension (repo rule: same change).
4. Verbatim sectionizer + its test.
5. Corpus manifest + ingest script + its test.
6. Concept seeder script.
7. Probe checklist doc + one-line inventory note in `supabase_migrations/README.md`.

### 7. Verification (the Phase 1 gate)

1. `python3 -m pytest tests/test_connection_map_*.py` green; full `python3 -m pytest
   tests/` green (no regressions).
2. Apply the 5 migrations to **sage-dev** in filename order via MCP `apply_migration`
   (they depend only on `auth.users`, none of the unseeded base tables — sage-dev's
   empty state does NOT block this). Verify each table with the REST 200/404 probe.
3. Run the full probe checklist via MCP `execute_sql`; every expected failure fails,
   every expected success succeeds; cleanup verified.
4. Run seeder + ingester against sage-dev (needs the sage-dev service key from the
   dashboard — 1-minute user op — or fall back to seeding via MCP `execute_sql`);
   spot-check counts (~72 concepts, 20 documents, sections' round-trip verified).
5. Prod application waits for the normal release flow — nothing in prod changes in
   Phase 1 until you say so.

### Open decisions (recommendations embedded — plan approval approves them)

1. **DB target**: sage-dev first (recommended, zero prod risk, unblocked despite the
   seeding blocker); prod only at release on your go.
2. **Tier CHECK ('A','B')** — deviation from the spec's A|B|C enum since tier C is
   "discarded, never queued"; widening the CHECK later is the established pattern if
   ever needed.
3. **7 concept additions** marked `spec_addition: true` (conflict #8) — reviewer sees
   them; nothing silently fixed.
4. **Zero-evidence rule enforced universally** — Phase 1 only produces
   literature_scan rows; if Pass 3 ever activates (flag-off, consent-gated), its edges
   still carry guideline evidence per §6.4, so no carve-out is needed.
5. **master_map_version immutability trigger deferred to Phase 3** (publication gate
   owns its semantics); interim CHECK only.
6. **Re-ingesting a cited document is FK-blocked** — citation integrity; unblocking is
   a governance action in a later phase, not a `--force` flag.

---

# Owner decisions after Phase 1 (2026-07-28)

Four directions from the product owner. All three spec changes are recorded here
because they modify SPEC-connection-map.md; the spec file itself is left as the
original v3 so the delta stays visible. Implement at the phase named, not before.

## D1. Loose re-check of physician edits (Phase 3)

**Direction:** when a physician edits a connection during review, re-check it
loosely against the guidelines. Anything clearly wrong goes back for approval
with a note. Most edits pass, because a qualified doctor made them.

**Scope boundary that must hold.** Two different things are editable and they
get opposite treatment:

- `patient_phrasing`, urgency, concept mapping, prevalence — the physician's own
  wording and metadata. **These get the loose check.** It runs the deterministic
  §8 copy lint (grade level, no em dashes, no causal verbs, no confidence
  numerals) plus a soft semantic check that the reworded question still reflects
  the cited quotation.
- `quoted_sentence`, `char_offset`, `source_section_id` — the citation itself.
  **These stay exact-match forever** (§16). The loose check never touches them
  and never becomes an alternative path to storing an unverified quote.

**Behaviour:** warn, never block; never auto-reject a physician's edit; the flag
is advisory and the physician decides. Same warn-never-block posture as the
report-scan name-mismatch warning already shipped. The checker can only flag —
it can never approve, and it is not an authority on clinical correctness.

**Note:** §5.6 already voids an attestation when an edge or its evidence changes
after signing. D1 sits BEFORE signing (during review), so the two do not
conflict; keep it that way.

## D2. Tier C redefined — kept, not discarded (Phase 1 schema + Phase 4)

**Direction:** "Nothing should have no verification. Redefine C tier to:
far-fetched non-word-for-word connection. Could hold major innovation, or be
useless. When a physician has ample time they will look at them."

**Supersedes** §4.4's "C — no verifiable quotation. Discarded, never queued" and
narrows §6.3's blanket rejection of unconstrained discovery.

**Design constraints that make this safe** (the spec's core guarantee must
survive the change):

1. A tier C edge MUST still reference real `source_section` rows — the passages
   it was inferred from. Traceability is not optional just because the wording
   is not verbatim.
2. A tier C edge MUST NOT carry a fabricated sentence presented as a quotation.
   Introduce `evidence_kind` ('verbatim' | 'inferred'); the exact-match trigger
   runs on 'verbatim' rows only, and 'inferred' rows carry the model's reasoning
   in a field that is never rendered as a quote. Tier A/B accept 'verbatim'
   only. This keeps "no fabricated citations" true, which is the property that
   actually matters — not "every row is verbatim".
3. Tier C is a separate, lower-priority review queue. It must never gate or
   delay the A/B launch queue.
4. **ANSWERED 2026-07-28: yes — an APPROVED tier C edge may reach a patient.**
   It goes through the identical gate as A/B: physician attestation, no
   exceptions, no separate path. C changes what may be *proposed* for review,
   never what may bypass review.

   **Consequence that lands in Phase 3 and needs legal input.** The §5.6
   attestation sentence reads "I attest that this statement is consistent with
   the cited sources." For tier A/B that is a verbatim quotation, so the
   physician is confirming something checkable. For tier C the sources do NOT
   say it word for word, so signing that same sentence claims more than the
   evidence supports. Either the attestation text gains a tier C variant naming
   the inference explicitly, or the reviewer is signing an overclaim. §5.6 says
   the text must not be altered without legal review, and this project already
   treats attorney-reviewed copy as a hard gate (consent copy). So: draft a
   tier C attestation variant, route it to the attorney with the consent-copy
   revisions, and do not ship C to patients until it is signed off. Not a
   Phase 2 blocker.

**Schema impact:** widens the `master_edge` tier CHECK to ('A','B','C') and adds
`evidence_kind`. `tests/test_connection_map_migrations.py::test_tier_cannot_store_c`
and `EDGE_TIERS` in `lib/connection_map/concepts.py` currently assert the
opposite and must flip WITH this change, deliberately and in the same commit.

## D3. Physicians extend the vocabulary (Phase 3)

**Direction:** physicians approve connections today; should they also add their
own concepts and/or approve AI-proposed ones?

**Answer: yes for concepts, no for relationship types.** See the response to the
owner for reasoning. Concretely:

- Review workspace gains "propose a concept", writing a `concept` row tagged
  with its physician author. Low risk: a concept is a noun and asserts nothing.
- AI-proposed concepts are allowed as PROPOSALS a physician approves, never
  auto-added — same posture as edges.
- The six relationship types stay a closed enum (§3 hard prohibition). Each type
  carries distinct semantics, patient-facing rendering, and validation rules
  (`acts_through` is never patient-facing at all), so adding one is a code and
  copy change with its own review, not data entry. A physician can REQUEST one;
  that becomes a change request, not a runtime insert.
- `display_patient` still requires physician wording before publication (§5.7).

## D4. Corpus acquisition (before Phase 4)

General survivorship sources are the owner's ask to the CEO, who is also the
attesting physician. Email drafted 2026-07-28. Targets: ASCO/ACS survivorship
care guidelines, late-effects, exercise/nutrition. Without them the §10.3
symptom-cluster half of extraction has no citable source and will underproduce.
