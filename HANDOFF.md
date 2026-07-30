# HANDOFF — active work

_Keep this for in-flight work only. Last updated: 2026-08-02._

## RESUME HERE — connection map: Phase 4 DONE, Phase 5 is a human task

**Phase 4's gate (≥60 candidates with verified evidence) is MET: 82 edges and
137 citations on sage-dev, every citation an exact match against source bytes.**
Phases 1-4 complete. 617 tests green. Prod still untouched; ~34 commits unpushed.

### What Phase 4 actually took (all four were invisible failures)

Extraction returned zero candidates AND zero rejections. Four separate defects:

1. **The extractor is a reasoning model.** On a real 12k-character section its
   thinking spent the whole token budget before one visible character, and under
   `response_format=json_object` the decoder must still return a valid object —
   so it returned `{"candidates": []}` in 7 tokens, or echoed the section back as
   `{"section_text": …}`. Fixed with `chat_template_kwargs={"enable_thinking":
   False}`. Raising max_tokens does NOT substitute (measured at 8000).
2. **Neither failure was visible.** Any unrecognised envelope became an empty
   list, so a broken extractor and a quiet corpus printed identically. Now
   counted as `unparsable_response` / `no_candidate_list` and printed per section
   as NO ANSWER.
3. **The prompt was tuned toward restraint** — worked examples replaced the
   repeated encouragement to return nothing.
4. **Direction was stated but not enforced**, so `weight_gain --side_effect_of-->
   nausea` (nausea as a treatment) was accepted. `RELATIONSHIP_DOMAINS` now
   enforces it in both passes.

Pass 2 hit the SAME collapse at scale: all 131 quotations in one call returned 7
tokens of nothing, six in one call produced a real chain. It now batches by
shared concept (a chain runs *through* a concept, so arbitrary chunking separates
the pairs that could combine).

### Where the map stands

- **82 edges, 137 citations.** 28 edges carry more than one citation; 21 are
  cited by more than one document.
- **Corroboration works** (D7): a second source stating a known relationship adds
  an evidence row instead of being discarded (52 added in one sweep, 62 already
  recorded and correctly skipped). Only `candidate` edges accept one — `edge_hash`
  covers every evidence row, so adding to a signed edge would void the signature.
- **3 tier B chains** from pass 2, each with 2 citations plus its reasoning,
  which the review API surfaces as `chain_reasoning` and the mobile card labels
  "Proposed reasoning, not a quotation".
- **Best corroborated:** bone mineral density loss ← aromatase inhibitor and
  neutrophil count ← anthracycline (6 citations from 4 documents each).

### CORRECTION to a previous handoff claim

This file said the spec's headline relationship — joint pain from aromatase
inhibitors — had **no official openly-accessible source**. That is wrong. Cancer
Pain (PDQ), Health Professional Version (NCI, a US government work) states it
outright: *"Among hormonal therapies, aromatase inhibitors cause musculoskeletal
symptoms, osteoporotic fractures, arthralgias, and myalgias.[34]"* The edge now
carries 5 citations, of which one is plainly wrong (it is about fracture
episodes, not joint pain) and should be rejected in review. The SECOND half —
joint pain as the reason women stop the drug — is still uncovered, and no
quotation in the corpus supports it.

**The peer-reviewed-sources question is CLOSED** (D7: they corroborate, never
carry a connection alone). Nothing is blocked on it.

### Next: Phase 5 is Dr. Csiki's, not code

Phase 5's gate is "v1 map published" and its work is 3-4 hours of clinical
review. Before handing it over:

1. **The reviewer UI has never run on a device.** It is the surface the whole
   phase depends on. Ship a build (or `eas update`) and walk the queue.
2. Decide whether to trim the queue first. 82 candidates at ~2 minutes each is
   ~3 hours, which matches the spec's budget, but the obviously-wrong ones (the
   fracture citation above, the `general_pain → work_status` chain that rests on
   a sentence attributing disability to the cancer rather than the pain) could be
   pre-rejected to spend that time better.
3. Tier C still cannot be signed: no attorney-approved attestation wording
   exists, and the API refuses rather than falling back (D2).

### Known gaps, still open

- **`concept` has no provenance column**, so a physician-proposed concept (D3)
  and stray probe data are indistinguishable. Two Phase 3 fixture concepts
  (`g_ai`, `g_joint_pain`) sat in the live breast vocabulary and extraction built
  five duplicate edges on them before this was caught. They are out of scope now
  and the duplicates are deleted, but add provenance before physicians start
  adding terms.
- **Attestation has no optimistic concurrency.** `connection_map_attest` computes
  `edge_hash` server-side at signing, so a reviewer who loads a candidate and has
  evidence added underneath them signs a hash covering a row they never read.
  Restricting corroboration to `candidate` edges does not close it, because
  candidates are what reviewers read. The fix is the queue returning `edge_hash`,
  the client sending it back, and the function refusing a mismatch.
- The two JCO-formatted PDFs are still column-interleaved (sidebar plus two body
  columns; `_gutter()` handles one clean split). Needs multi-zone detection.

### Where the durable facts now live (do not re-derive)

`.claude/rules/connection-map.md` — every invariant: exact-match citations,
re-anchoring, the PHI boundary and its import rule, corpus-ingest failures
(column interleaving, lost word spacing, NCI patient-vs-HP versions), the
reasoning-model call config, how to read a zero-candidate run, the batching rule
for both passes, and the corroboration path.
`.claude/rules/supabase-migrations.md` — probe as the app's role rather than as
postgres; `BEFORE DELETE` triggers must `RETURN COALESCE(NEW, OLD)` or they
cancel the delete silently; constraint-name collisions; pinned search_path;
cardinality vs array_length.

Env for any connection-map script: `set -a; . ./.env.development; set +a`, then
take ONLY `TOGETHER_API_KEY` from `.env` — sourcing all of `.env` breaks the DB
connection.

## Everything else on the connection map

Phases 1-3 are COMPLETE and adversarially reviewed (schema, corpus store,
reviewer roles + `sage_review` PHI boundary, attestation, publication gate,
mobile review workspace + publish screen). Applied to **sage-dev only — prod
untouched**. Probe checklists: `docs/connection_map/phase{1,2,3}_probe_checklist.md`.
Plan, decisions D1-D7 and the 12 spec-vs-repo divergences: `PLAN.md`.

Corpus: 29 documents, 896 sections, ingested with BOTH extraction fixes
(two-column gutter detection AND `x_tolerance=1`, without which journal PDFs
lose word spacing entirely). Do not re-ingest.
Screen preview for design review (published artifact):
https://claude.ai/code/artifact/7edcc192-e3ba-4ef3-8b36-451f3f1ce333

**Still unproven:** the patient-side half of reviewer/patient account
exclusivity (needs `patient_profiles`, absent on sage-dev); acceptance #2's
route test lands with real reviewer traffic. **Not built at all:** every
patient-facing surface (Phases 7-9) — the question in chat, the honesty
commitment, the revision view.

**Security:** `.env.development` holds a real sage-dev service-role key and is
gitignored (`.env.*`). The owner should rotate it — it was pasted in a chat.

## Standing operations
- Weekly `python3 scripts/modeler_report.py --all` AND
  `python3 scripts/safety_report.py` → Dr. Csiki packet.
- All lifecycle + safety flags live in prod; `SAFETY_CLASSIFIER_ENABLED=false`
  is the safety-layer kill switch (floor-only).
- After any deploy touching bundling: check `/api/health` →
  `prompt_files: 12, overlays: 10`.

## Blockers / waiting on people
- **Physician review of `config/safety/sage-safety-rules-v0.9.json` = LAUNCH
  BLOCKER** before real patients (Dr. Csiki proposed; asked in the 2026-07-21
  supervisor email).
- sage-dev seeding needs the prod DB password → steps in
  `supabase_migrations/README.md` (project `eizhshntrquvqwfsseeh`, $10/mo).
- Supervisor open questions (SAGE_TODO): entity branding, mysage.chat DNS,
  pilot recruiting timing. Trademark check runs later (not blocking builds).

## Shipped reference (details live in SAGE_TODO + memory, not here)
- **Build #34 installed + device-verified 2026-07-27**: report-scan photo OCR
  end-to-end (9/9 findings, labs display-only, de-id held). The #32 crash
  saga is CLOSED — every lesson (autolinking silent skip, Metro fatal on
  factory throws, binary strings gate, iOS 16 floor, Apple Vision engine,
  OTA `--platform ios`) lives in `.claude/rules/mobile-ui.md` + CLAUDE.md.
  Builds #32/#33 superseded; buildNumber 34 committed (`d02c601`).
- Safety layer LIVE 2026-07-22 (tiers, audit table, eval gate 100%); Flask
  boundary CONFIRMED permanent by supervisor; guidelines adoption done
  (accounts split, AI_CALL telemetry, prompts-as-files, direct supabase-js
  phone OTP — Flask `/api/auth/phone/*` deprecated, DELETE next release).
- Glossary (`glossary_terms` in prod, explain + CRUD endpoints) verified
  end-to-end in prod 2026-07-26.
- Report-scan backend deferred-to-v1.1 items: report-extraction eval suite;
  labs.* namespace.
- Legacy `handle_new_user` trigger fixed 2026-07-25 (unused `user_profiles`
  table 500'd all phone signups — falls back to auth uid now).

## Next follow-up eval windows (one variable each)
1. Voice rules into the system prompt (no em dashes + sixth-grade — Kimi still
   emits em dashes); prompt changes must bump SHA pins.
2. Modernize `scripts/test_all_features.py` literal-substring checks
   (6 known artifacts, SAGE_TODO Workstream C).

## Open follow-ups (unstarted, still valid)
- Learning-loop activation (attorney checklist in docs/compliance/).
- Web SPA parity (chips are mobile-only; web ignores pending_confirmations).
- Retire `chat_messages` double-write + legacy endpoints once old builds age out.
- Delete the dead duplicate Vercel project (`wondrchat-nine.vercel.app`).
- RLS enable+policy migrations for core tables (patient_profiles,
  conversations, messages — currently service-role-guarded only).
- Consent-management UI: verify withdraw/restore end-to-end.
