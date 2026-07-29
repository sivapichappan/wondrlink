# HANDOFF — active work

_Keep this for in-flight work only. Last updated: 2026-07-31._

## RESUME HERE — connection map Phase 4 (extraction)

**State: everything is built and tested; the blocker was corpus content, and
six new documents have just been staged to fix it.**

### THE ONE REMAINING BLOCKER: the prompt is too conservative

Corpus is now good and the pipeline is proven; extraction still returns
**zero candidates, and zero rejections**, even on clean NCI health-professional
sections with high concept density. Zero rejections is the tell: the model is
not proposing anything at all, rather than proposing things that fail checks.

`config/connection_map/prompts/pass1_section.md` is over-tuned toward restraint.
It says, repeatedly, "an empty list is far more useful than a strained one",
"only propose a relationship you can point at a single real sentence for",
"if you find yourself editing a sentence to make it fit, that candidate does
not belong". DeepSeek-V4-Pro obeys all of it maximally.

**Next actions, in order:**
1. Rebalance that prompt. Keep the exact-quotation rule absolutely (it is the
   feature's whole guarantee, and the validator enforces it regardless), but
   drop the repeated encouragement to return nothing. Add 2-3 WORKED EXAMPLES
   showing a real source sentence and the candidate it should produce —
   few-shot will move this further than more instruction.
2. Verify against a section known to contain a qualifying sentence, e.g.
   Cancer Pain PDQ `s0014-overview`, or Nausea PDQ sections.
3. If the prompt alone does not move it, try a second model
   (`MODEL_CONNECTION_EXTRACTOR=...`, e.g. Kimi-K2.6) before changing anything
   structural. Change ONE variable per run.
4. A useful smoke test that needs no model: `validate_pass1` already accepts
   hand-written candidates, so a fixture proves the write path end to end.

### Corpus state (good — do not redo)

29 documents, **896 sections**, all re-ingested 2026-07-31 with BOTH fixes:
two-column gutter detection AND `x_tolerance=1` (journal PDFs otherwise lose
word spacing entirely — 28% run-together words in the ACS/ASCO guideline).
Nine survivorship/symptom documents added; measured ~108 side-effect and ~182
co-occurrence qualifying sentences.

**Known remaining corpus defect:** the two JCO-formatted PDFs
(`asco_cipn_guideline_2020.pdf`, `acs_asco_breast_survivorship_2016.pdf`) are
still interleaved — their pages have a sidebar plus two body columns, and
`_gutter()` only handles a single clean split. Prefer the NCI PDQ documents,
which are clean. Fixing JCO needs multi-zone column detection.

### What to do next, in order

1. **Add the 6 new documents to `config/connection_map/corpus_manifest.yaml`.**
   Already copied into `data/` and verified to extract cleanly:

   | file | scope | cancer | side-effect sentences | co-occurrence |
   |---|---|---|---|---|
   | `asco_cipn_guideline_2020.pdf` | general_survivorship | null | 27 | 5 |
   | `nci_lymphedema_pdq.pdf` | general_survivorship | null | 8 | 16 |
   | `nci_hot_flashes_night_sweats_pdq.pdf` | general_survivorship | null | 8 | 23 |
   | `acs_asco_breast_survivorship_2016.pdf` | cancer_specific | breast | 5 | 14 |
   | `nci_fatigue_side_effects.pdf` | general_survivorship | null | 3 | 8 |
   | `nci_cardiopulmonary_pdq.pdf` | general_survivorship | null | 0 | 1 |

   Titles/publishers: ASCO CIPN Guideline Update 2020 (Loprinzi et al., author
   manuscript via Indiana ScholarWorks); NCI PDQ Lymphedema / Hot Flashes and
   Night Sweats / Cardiopulmonary Syndromes; ACS-ASCO Breast Cancer
   Survivorship Care Guideline 2016 (Runowicz et al.); NCI Fatigue and Cancer.

2. `set -a; . ./.env.development; set +a` then
   `export TOGETHER_API_KEY="$(grep -E '^TOGETHER_API_KEY=' .env | head -1 | cut -d= -f2- | tr -d '\"'"'"' ')"`
   — sourcing ALL of `.env` breaks the DB connection; take only the model key.
3. `python3 scripts/ingest_connection_map_corpus.py` (new docs only ingest).
4. `python3 scripts/run_connection_map_extraction.py --pass 1 --limit 12` first,
   inspect, then drop `--limit` for the full run. Then `--pass 2`.
5. Gate: **60+ candidates with verified evidence.** 51+67 qualifying sentences
   are available, so this may land just short — see "if short" below.

### If the run falls short of 60

Three documents the research recommended were NOT saved and are the obvious
top-up, measured from their HTML: **Nausea and Vomiting PDQ (29 side-effect
sentences — the single richest), Pain PDQ (8), Cognitive Impairment PDQ (2)**.
All at `cancer.gov/about-cancer/treatment/side-effects/...-hp-pdq`. Also note
the saved Fatigue file is the SHORT patient page (3 sentences); the
health-professional PDQ version scored 23.

### Open decision for the owner

**Do peer-reviewed open-access reviews count as sources?** The spec's most
important relationship — joint pain from aromatase inhibitors, and joint pain
as the leading reason women stop taking them (§10.2 and §10.3) — has NO
official openly-accessible source; every ASCO guideline covering it is
paywalled. Two CC-BY reviews cover it exactly (Frontiers in Endocrinology 2021
PMC8353230; Rheumatology Advances in Practice 2024 PMC11003819, which contains
"joint pain is noted to be the most common reason for ceasing AI therapy").
Recommendation given: accept them, tagged as a lower source tier shown on the
review card, since the physician signs each connection anyway. NOT YET ANSWERED.

### Hard-won facts, do not rediscover

- **Never trust a researcher's "verbatim" quote.** The one supplied for the
  lymphedema PDQ is not in the document. The document is still good.
- **PDF column interleaving** silently shredded the original patient
  guidelines; `_gutter()` in the ingest script fixes it. A FINISHED ingest
  proves nothing about text quality — grep the stored text for a real sentence.
- **Concept aliases matter more than the class names.** Drug names appear more
  often than classes (paclitaxel 44 sections vs taxane 30).
- The extractor correctly returns nothing for bibliographies, trial-results
  tables, and generic "side effects of treatment" copy. Zero candidates is
  often right; check WHICH sections were read before touching the prompt.

## Everything else on the connection map

Phases 1-3 are COMPLETE and adversarially reviewed (schema, corpus store,
reviewer roles + `sage_review` PHI boundary, attestation, publication gate,
mobile review workspace + publish screen). 552 tests green. Applied to
**sage-dev only — prod untouched**, and 27+ commits are UNPUSHED.
Probe checklists: `docs/connection_map/phase{1,2,3}_probe_checklist.md`.
Plan, decisions D1-D6 and the 12 spec-vs-repo divergences: `PLAN.md`.
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
