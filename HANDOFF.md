# HANDOFF — active work

_Keep this for in-flight work only. Last updated: 2026-08-03._

## RESUME HERE — the reviewer app is built; the next step is a device

**Phase 4 is done and Phase 5 is prepared. 76 of 81 candidates are ready to
approve AND publish; the remaining 5 wait on one concept name (below). 644 tests
pass, tsc clean, Pressable scan clean. Prod untouched; 39 commits unpushed.**

### THE NEXT ACTION IS TO PUT IT ON A PHONE

Nothing in the reviewer workspace has ever rendered on a device, and it is the
surface a physician will sit in for 3-4 hours. `eas update --channel production
--platform ios` (JS only, no build needed), then walk several real cards through
approve, reject and reword. Specifically worth testing by hand, because no
mobile test framework exists:

- background the app for a few minutes, come back, and confirm the session still
  works (this was silently broken until the AppState wiring landed);
- kill wifi mid-decision and confirm the message says nothing was signed;
- the reword keyboard, on a card that is not the first one.

### What was fixed this session

**You cannot sign, or change, what you did not see.** `connection_map_attest`
computed the edge hash AT signing time, so a citation added between opening a
card and signing it landed inside a signature nobody had read. The queue now
hands out each edge's hash, the client returns it, and the function refuses a
mismatch (`STALE_EDGE`, 409). The old unpinned 7-arg form is dropped, not
overloaded, so no caller can skip it.

A second instance of the same bug was worse and reachable from the UI: `edit_edge`
had no status check at all, so rewording an approved edge voided its signature in
silence, surfacing only later at the publication gate as "attestation voided". A
trigger now freezes the hash-bearing columns once an attestation exists;
`status` and `rejection_reason` stay editable, because approving is what signing
does and a physician may still change her mind.

**There was nothing to review.** All 81 candidates had empty `patient_phrasing`
and all 60 concepts had no `display_patient`, and Approve is disabled without
wording — so the queue would have opened with nothing approvable and 141 strings
to hand-author on a phone. `scripts/draft_connection_map_wording.py` drafts both,
gated on the same copy lint the publication gate applies; failures are left blank
rather than shown as a starting point.

**The queue was built for browsing, not for a long sitting.** Rewritten as one
card at a time with progress, Previous and Skip. Reject is now two deliberate
taps like Approve (it was one tap on one of eight 36pt buttons, irreversible).
Keyboard handling, pull-to-refresh, retry, specific error messages, role
awareness, sign-out, and AppState token refresh all landed with it.

### Acceptance #2 is now PROVEN, and probing it found a hole

With the dev secrets in place the real `/api/review/queue` was run against
sage-dev through the restricted `sage_review` connection, with the privileged
clients patched to explode if anything touched them: 200, 81 items, every one
carrying a hash, and the privileged clients never called. Signing with a stale
pin returned 409 and signing with no pin returned 400, both with nothing written.

Probing the other half of the boundary — trying to cross it rather than reading
the grant list — found that `sage_review` held **table-wide UPDATE on
master_edge**, so the restricted connection could set `status='approved'` with no
attestation behind it. The probe did exactly that and left a real edge approved
and unsigned (restored immediately). The API always refused it, which meant the
guarantee rested on one Flask handler; the publication gate caught the orphan,
which is defence in depth working, but that is the wrong last line to rely on.
The grant is now column-scoped to what the code always claimed, and a test
compares the two lists.

### Known gaps, in the order they will bite

1. **`trastuzumab` has no patient-facing name**, which blocks 5 of 81 cards from
   PUBLISHING (they can still be approved). The drafting model keeps reaching for
   "targeted therapy for HER2 positive cancer" and the jargon gate keeps refusing
   it. A clinician should name it. The card now says so rather than letting it
   surface at publish time.
2. **PROD needs `SUPABASE_JWT_SECRET` and `SUPABASE_KEY` set in Vercel**, or the
   review API returns 503 there exactly as it did locally. Dev is now configured
   and acceptance #2 is PROVEN against a real database (below); production is
   not, and the reviewer app cannot work there until those two are set.
3. `publish.tsx` is unreachable dead code — nothing produces a `versionId`, and
   publishing is admin-only while attesting is physician-only. Phase 5 ends with
   a published version, so this needs a route before then.
4. `concept` still has no provenance column, so a physician-proposed name (D3)
   and a pipeline-drafted one are indistinguishable once stored.

### Old context, still true

## Phase 4 as it happened

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
