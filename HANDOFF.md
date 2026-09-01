# HANDOFF — active work

_In-flight work only. Durable facts live in `.claude/CLAUDE.md` and
`.claude/rules/`; decision records are in auto-memory
(`project_trajectory_pivot`, `project_design_paper_lamplight`,
`infra_provider_model_retirement`). Last updated: 2026-09-01._

## RESUME HERE — device testing, then night mode

Everything below the line is SHIPPED and prod-verified. Nothing is
half-finished; the next move is a person looking at a phone.

**1. Device testing — the only real blocker on knowing whether any of this
worked.** Nothing in the redesign, the retheme or the motion layer has been
witnessed on a handset. Two instruments now exist and they are for different
jobs:

- **The Alvarez Folder** (2026-09-01) is the one for judging the PRODUCT:
  one patient, eight sittings, six scannable documents, an arc that
  accumulates. https://claude.ai/code/artifact/8a6b05c4-448b-4f36-8c1e-b30730ea3073
  Source `docs/testing/persona-maria-alvarez.md`; documents in
  `docs/testing/documents/` (verified by `scripts/check_persona_documents.py`);
  replay via `scripts/reset_test_patient.py`. The end state is MEASURED, not
  estimated: coverage 45% → 87%, 4 → 8 known, lifecycle → trial_ready, and
  the check-in swaps from nausea/eating/neuropathy to joint aches/hot flashes
  when the regimen changes.
- The 49-check walkthrough stays for regression-probing ONE path after a
  change: https://claude.ai/code/artifact/d107db38-ea5b-41a8-9d0c-4748b5921888
  Sections A-C (walls, default-engage, near-misses that must NOT wall) are its
  highest-value part. The owner's verdict on it as a product test was that the
  questions were "random sporadic" and built no patient foundation — which is
  what the persona kit answers.

**2. Night mode.** `mobile/constants/theme.night.ts` holds contrast-checked
values and is deliberately NOT wired — see `project_design_paper_lamplight`
for the two routes and why `DynamicColorIOS` was not taken. Needs `app.json`
off `userInterfaceStyle: "light"`, so **a real build, not an OTA**, and its
own device pass.

**3. Physician review of `config/safety/sage-safety-rules-v0.9.json` — still
the LAUNCH BLOCKER**, carrying the fail-open evidence (under a rate limit,
LLM-only cases silently become NONE: "dizzy, black stools" → NONE). The brief
makes this RECURRING editorial labour, not a one-time signoff; the owner still
needs to decide who owns that queue. `config/check_in/questions.json` is
owner-approved (2026-08-26) but has NOT had a clinician's eyes.

**4. Card telemetry has no reader.** `patient_events` type `card_engagement`
records shown/acted/dismissed per card kind. The brief's stated risk is that
underperforming cards starve scanning and trials never unlock — this is the
instrument for it and nobody has looked. A weekly count by kind would answer it.

## Shipped and verified

| What | When | Evidence |
|---|---|---|
| The five redesign changes | 2026-08-26 | backend `a579c1e`; prod-probed (new routes 401 vs a 405 control; the prognosis wall and the birthday-party question both confirmed on a real account) |
| 28 adversarial-review fixes | 2026-08-26 | incl. a critical one: every clinician would have been shown the PATIENT consent |
| Paper and Lamplight + motion | 2026-08-28 | OTA `3683c29` |
| Dismissible AI notice, chips stop speaking jargon | 2026-08-30 | OTA `e39de5f` |
| Composer sits on the keyboard | 2026-08-31 | OTA `070743b` |

Suite at last check: 1110 backend tests, tsc + lint clean, NativeWind
Pressable scan zero, EAS bundle green.

## Production state

- Prod runs the post-retirement model set (see
  `infra_provider_model_retirement`). Chat answers; the classifier tiers.
- `FEATURE_PUSH_NOTIFICATIONS=true`, but `device_push_token` has 0 rows —
  nobody has opted in and nothing has ever been sent.
- Breast test patient `sage.test.breast@example.org` /
  `SageBreastTest2026!`. **Reset to the bare fixture 2026-09-01** (sitting-1
  state for the persona kit: stage IIB, NO zip, NO treatments, NO biomarkers,
  coverage 0.45, cooldowns clear). Chat history was NOT cleared; run
  `reset_test_patient.py --full --clear-chat` before starting the arc.
- **Design revert is one command**: `mobile/constants/theme.v1.ts`, or the tag
  `design-v1-approved-mockups` for the whole app at that point.

## Carried, deliberately not done

- The drawer's "All tools" launcher survives; the nine-tool HOME grid is gone.
  It stays until cards cover what it holds, because deleting it now would
  strand real features.
- Deep research keeps its own off-topic gate (three surfaces consume that
  contract); revisit with its tool decision.
- `/api/screening/save` + the screening tables stay server-side for the web
  SPA's parity pass; only the mobile questionnaires were deleted.
- Rule 1's sixth-grade readability gate in CI is NOT built. Copy is written to
  the standard and guarded by tests for dashes, directives and jargon, but
  nothing measures reading level.
- "Since your last visit" compiler, the allowlisted ingestion pipeline and
  appointment-date awareness (the brief's below-the-top-five items).
- The web SPA never received the redesign at all — zero of the new tokens,
  still on the old palette. Phone-first per the standing convention; web
  parity is its own project.

## Blockers / waiting on people

- **Rotate the sage-dev service-role key** (pasted in a chat once).
- **Email pipeline** (custom SMTP + templates + "Confirm email") — user-side.
- Test accounts still in prod: `test.doctor.a@`, `test.doctor.b@wondrlink.com`,
  `sage.test.breast@example.org` — delete when device testing is finished.
- (Physician review of the safety rules is item 3 under RESUME HERE.)

## Connection map — unchanged, untouched

81 candidates, 0 approved. Machinery proven end to end; the queue needs Dr.
Csiki's sitting. 22 concepts lack `display_patient` (blocks publishing);
`publish.tsx` unreachable. NOTE: the redesign's rule 8 ("every sentence traces
to a signed source") makes this pipeline the long-term answer-source — its
priority likely RISES with the pivot.

## Found by the persona kit — small, unowned, real

1. **The report extractor times out more often than it succeeds under load.**
   `EXTRACTOR_TIMEOUT_S = 10` (`lib/patient_model.py`); measured median 8.5s
   over nine no-timeout calls, 4 of 9 over the limit, tail to 87s. The SDK
   retries twice, so a scan takes ~30s and then reports **"No medical facts
   found in that text. Try a clearer photo of the results section"** — blaming
   the patient's photograph for a server timeout. Raising the timeout is a
   product decision (it interacts with the Vercel function limit and with how
   long the review screen spins), so it is NOT changed. Owner's call.
2. **`ECOG unspecified` always appears on the My Care card.**
   `lib/profile_utils.py:569` builds `performance_status` as an f-string
   BEFORE the `!= 'unspecified'` test, so the test can never suppress it — and
   the UI is not supposed to say ECOG at all.
3. **The surveillance screen reads keys the server does not send** — server
   `type`/`recommendation`/`next_due`, client `test`/`when`/`due_date` — so
   even a correctly generated colorectal schedule renders blank rows.

FIXED 2026-09-01: the PII guard's `street_address` pattern used `\s*` between
street-name words, so `greatest` split into `greate` + `st` and **"2.6 cm in
greatest dimension" read as a street address**. That phrase is boilerplate in
every pathology report, so photographing a real one 422'd outright. One
character in `lib/deidentify.py`, locked by two tests both directions.

## Open eval windows

- `soften_tone`'s clause-blind regexes ("you should've" → "it might help
  to've"; "you must not X" → a weak suggestion). Load-bearing now that the
  walls use fixed template sentences.
- Colorectal-only prompt blocks that are not gated on `cancer_slug`.
- `scripts/test_all_features.py` literal-substring modernization.
- The verifier (`gpt-oss-20b`) and glossary (`gpt-oss-120b`) shipped
  unvalidated after the provider retirement; both fail open harmlessly, but
  neither has been spot-checked.

## Standing operations

- Weekly `python3 scripts/modeler_report.py --all` + `safety_report.py` → Dr.
  Csiki packet.
- `SAFETY_CLASSIFIER_ENABLED=false` = safety-layer kill switch (floor-only).
- Deploy checks: match the commit SHA (a 200 on `/api/health` is the PREVIOUS
  deployment, and it never touches a model, so it stayed green through the
  provider outage); `prompt_files: 12, overlays: 10` after bundling changes;
  `eas update:list --branch production` for what the phone will actually get;
  native module builds gated on `strings` over the `.ipa` binary.

## Where the durable facts live (do not re-derive)

`.claude/rules/` — mobile-ui (NativeWind trap, RN-selectable truth,
typographer, binary gate, the keyboard/safe-area double-inset, PressableScale,
motion tokens, no delight budget, disclosure-may-be-reduced-not-removed),
backend-python (enforce_voice, depth levels, de-identify strip list,
throttled-eval trap, walls-are-the-only-gate, chips-never-lead-with-jargon,
model_state merge), prompt-files (whitespace, register), supabase-migrations
(probe-as-role, CAS patterns), connection-map.
`PLAN.md` + `SPEC-connection-map.md` — connection map. `SAGE_TODO.md` — the
older checklist; its Workstream D (plain-language mappings) is largely
absorbed by the trajectory brief.
