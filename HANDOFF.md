# HANDOFF — active work

_In-flight work only. Durable facts live in `.claude/CLAUDE.md` and
`.claude/rules/`; the redesign decision record is in auto-memory
(`project_trajectory_pivot`). Last updated: 2026-08-24 (evening)._

## INCIDENT 2026-08-24 — provider model retirements took prod chat DOWN (RESOLVED)

Discovered via a failing llm-mode eval, confirmed end-to-end against prod:
**Together moved `moonshotai/Kimi-K2.6` to dedicated-endpoints-only** (serverless
400s) and **Groq retired every Llama model** including `llama-3.3-70b-versatile`
(classifier/glossary/fallback) and `llama-3.1-8b-instant` (verifier). Every
patient question hitting the LLM 500'd, and the safety classifier's judgment
layer silently failed open to the keyword floor on every message.

**Fix (live + probe-verified):** env overrides on the EXISTING prod deployment
(`vercel env add` × 7 + `vercel redeploy` of the old build — no new code
shipped): chat + chat_together → `meta-llama/Llama-3.3-70B-Instruct-Turbo` on
Together (the registry's own documented rollback voice); classifier →
**same model on Together** (`MODEL_CLASSIFIER_PROVIDER=together` — the 2026-07-21
bake-off alternate; re-validated 12/12 tier accuracy, zero under-escalation,
before shipping); glossary + fallback → `openai/gpt-oss-120b` on Groq;
verifier → `openai/gpt-oss-20b` on Groq. Verified in prod: real chat answer
(api_used together) AND the fever-on-treatment case tiers T2 with the card.
Local `.env` mirrors the overrides (commented block at the bottom).

**DECIDED 2026-08-26 (owner): keep the pre-Kimi voice.** Llama-3.3-70B on
Together is now the registry DEFAULT, not just an env override (1bae699), so
a fresh environment no longer resolves to a model that 400s. Restoring Kimi
needs a paid dedicated endpoint plus `MODEL_CHAT=moonshotai/Kimi-K2.6`.

Still worth knowing:
- The verifier (`gpt-oss-20b`) and glossary (`gpt-oss-120b`) shipped
  unvalidated (both fail open harmlessly); worth a spot-check.
- Any llm-mode eval baseline from the Kimi era is now cross-model — do not
  compare numbers across 2026-08-24 without noting the voice change.

## RESUME HERE — ALL FIVE CHANGES BUILT; review + push are what remain

The whole redesign is implemented locally: **19 commits, nothing pushed**
(owner decision on record: one cohesive update, not five). 1104 offline
tests, mobile tsc clean, EAS bundle repro green after every mobile change.

| # | Change | Commits | State |
|---|--------|---------|-------|
| 1 | Gate inversion (walls, default-engage) | 85b7777..0a8b220 | built + adversarially reviewed (28 findings fixed) + evals green |
| 2 | Kill the builder | dd29639, 0012266 | built |
| 3 | Design system + Home is the conversation | 9ff441a, 4115af4 | built |
| 4 | Check-ins as chat questions | 7a80114 | built |
| 5 | Onboarding = 3 screens + conversation | c1c8941 | built |
| — | Review fixes across 2-5 | 2635c9d | 31 confirmed findings fixed |

**Next steps, in order:**
1. ~~Adversarial review of changes 2-5~~ DONE (2635c9d): six lenses, 42
   findings, 31 confirmed and all fixed. It caught a CRITICAL bug in change
   5 (the reviewer-intent flag was cached at mount, before the tap that
   sets it could happen, so every clinician would have been shown the
   PATIENT consent — and completing it permanently bars the account from
   ever being a reviewer), the per-session AI disclosure scrolling out of
   sight at launch, "New chat" becoming a no-op, and the mockup's lightest
   ink failing WCAG AA wherever this app uses it for real text.
2. **SHIP IT — backend first, then the phone.** The two halves cannot go
   separately: the new app calls `/api/checkin/due`, `/api/events/card` and
   `/api/account/perspective`, none of which exist in prod yet.
   a. `git push origin main` → Vercel auto-deploys (~40s). Verify by the
      commit SHA, never by a 200 on `/api/health`.
   b. `cd mobile && eas update --channel production --platform ios`.
      **No TestFlight build is needed**: app.json's runtimeVersion policy is
      `appVersion` (1.2.0) and the last good build is runtime 1.2.0 on the
      production channel, so the OTA reaches the installed TestFlight app.
      Everything in the redesign is JS + font assets; app.json is untouched
      and no native module was added. A build is only needed if the app is
      no longer installed.
   c. Two cold launches on the phone to pick the update up.
3. **DEVICE TESTING** (the owner can only see it on a phone). Highest-risk
   unwitnessed paths: first launch through the name card; Home rendering a
   long existing thread; the check-in card's one-at-a-time sends; the new
   palette in daylight; and the walls (ask "How long do I have?").
4. Physician review of `config/safety/` — still the standing launch blocker.
   `config/check_in/questions.json` is OWNER-APPROVED (2026-08-26); if the
   safety review establishes that patient-facing question banks need a
   clinician's signature too, that file needs its own pass.

**Carried, deliberately not done:**
- The drawer's "All tools" launcher still exists. The brief cuts the nine-tool
  HOME grid, which is gone; the launcher stays until cards cover the tools it
  holds (previsit, glossary, appeal, deep research, check-up schedule),
  because deleting it now would strand real features.
- `/api/screening/save` and the screening tables stay server-side for the web
  SPA's parity pass; only the mobile questionnaires were deleted.
- Deep research keeps its own off-topic gate (its status contract is consumed
  by three surfaces); revisit when its tool decision is made.
- Rule 1's sixth-grade readability check in CI is NOT built. Copy was written
  to the standard and is guarded by tests for dashes/directives/jargon, but
  there is no automated readability gate yet.
- "Since your last visit" compiler, the allowlisted ingestion pipeline and
  appointment-date awareness (the brief's below-the-top-five items) are
  untouched.

### The five changes as built

1. **Gate inversion.** `lib/walls.py` — deterministic prognosis/diagnosis/
   dosing detection; direct personal-prognosis asks get the fixed screen-12
   card (tier NONE + no detected urgency); everything else gets the wall rule
   appended LAST to the prompt plus `enforce_wall()` guaranteeing the limit
   sentence in code. Off-topic refusal deleted from chat + sandbox.
   `engagement.yaml` (x10 cancers) + `wall_accuracy` metric replace the
   off_topic suite.
2. **Builder dead.** build.tsx (1014 lines) + the first-launch setup modal
   deleted; entry points point at scan/chat; trials ask is screen-09 copy
   with Scan a report / Just tell me / Not now.
3. **Design system + Home.** Mockup tokens in `mobile/constants/theme.ts`;
   Source Serif 4 is Sage's voice, Instrument Sans the interface; the
   patient's bubble is the one warm element. `ConversationSurface` shared by
   Home and /chat/:id; `DealtCard` + `/api/events/card` telemetry; the "+"
   sheet holds exactly Scan a report / Record a visit / Since your last visit.
4. **Check-ins.** `config/check_in/questions.json` (clinician-reviewable
   bank, caregiver variants written out) + `lib/check_in.py` (<=3 questions,
   treatment-tied first, 7-day cooldowns, decline counts) +
   `/api/checkin/due|record` + CheckInCard. Answers go through /api/chat ON
   PURPOSE — that is where PHQ-9 Q9's self-harm detection went.
5. **Onboarding.** Fork + basics form deleted; "For oncologists" footer link
   carries the reviewer intent so a clinician still never sees the patient
   consent; NameCard asks the name in the conversation; new
   `/api/account/perspective` + `perspective_set` so the gate waits on the
   question rather than on a name.

### Cross-cutting

- The 9 communication rules (memory `project_trajectory_pivot` has them
  compressed; the brief is authoritative). Rule 1's CI readability gate is
  still UNBUILT — see "Carried, deliberately not done" above.
- **Full retheme: DONE** (9ff441a) — mockup tokens in
  `mobile/constants/theme.ts`, Source Serif 4 as Sage's voice, Instrument
  Sans as the interface, warm `#F1E9DC` reserved for the patient's own words.
- `soften_tone`'s grammar-blindness ("you shouldn't" → "it might help ton't")
  becomes load-bearing under rule 3's fixed templates — fix it early.
- The frozen legal layer is explicitly out of scope for the redesign.

## Production state (all verified)

- **Prod is on the model overrides above** (redeploy `wondrchat-clrgghsb1`,
  2026-08-24): chat answers again, classifier tiers again. The gate
  inversion is NOT deployed (local commits only) — prod still runs the old
  off-topic gate until the owner says push.
- **The chat-UX wave is fully live**: backend deployed (probe-verified by
  401-on-new-routes vs 405 control) AND the OTA ran. `chat_turn` shows real
  usage (2 answered rows) — silent recovery works in prod. Still unwitnessed
  on a device: drag-selection in the select-text sheet, and any push actually
  landing on a handset.
- `FEATURE_PUSH_NOTIFICATIONS=true` is active in prod, but `device_push_token`
  has 0 rows — nobody has opted in, nothing has ever been sent.
- Breast test patient: `sage.test.breast@example.org` / `SageBreastTest2026!`
  (password reset 2026-08-08; profile + 4 conversations preserved).
- Product-foundations report (the redesign's evidence base):
  `~/Downloads/sage-product-foundations.md` + artifact
  https://claude.ai/code/artifact/952aab65-2766-4b80-85ad-f1f33badecdf

## Blockers / waiting on people

- **Physician review of `config/safety/sage-safety-rules-v0.9.json` = LAUNCH
  BLOCKER**, carrying the fail-open evidence (under a Groq rate limit,
  LLM-only cases silently become NONE; "dizzy, black stools" → NONE). Note the
  brief makes this RECURRING editorial labor (library re-review), not a
  one-time signoff — owner to decide who owns that queue.
- **Rotate the sage-dev service-role key** (pasted in a chat once).
- **Email pipeline** (custom SMTP + templates + "Confirm email") — user-side.
- Test accounts still in prod: `test.doctor.a@`, `test.doctor.b@wondrlink.com`,
  `sage.test.breast@example.org` — delete when device testing is finished.

## Connection map — unchanged, untouched

81 candidates, 0 approved. Machinery proven end to end; the queue needs Dr.
Csiki's sitting. 22 concepts lack `display_patient` (blocks publishing);
`publish.tsx` unreachable. NOTE: the redesign's rule 8 ("every sentence traces
to a signed source") makes this pipeline the long-term answer-source — its
priority likely RISES with the pivot.

## Eval windows that survive the pivot

- `soften_tone` negation/contraction suite (see Cross-cutting — now urgent).
- Colorectal-only prompt blocks gated on `cancer_slug` (probed at walkthrough
  Q28/Q50; also called out in the brief's defect list).
- `scripts/test_all_features.py` literal-substring modernization.
- (Superseded by change 1: the `classify_query_type` vocabulary item and the
  off-topic keyword fix — do not do them separately.)

## Standing operations

- Weekly `python3 scripts/modeler_report.py --all` + `safety_report.py` → Dr.
  Csiki packet.
- `SAFETY_CLASSIFIER_ENABLED=false` = safety-layer kill switch (floor-only).
- Deploy checks: match the commit SHA (a 200 on `/api/health` is the PREVIOUS
  deployment); `prompt_files: 12, overlays: 10` after bundling changes; native
  module builds gated on `strings` over the `.ipa` binary.

## Where the durable facts live (do not re-derive)

`.claude/rules/` — mobile-ui (NativeWind trap, RN-selectable truth,
typographer, binary gate), backend-python (enforce_voice, depth levels,
de-identify strip list, throttled-eval trap), prompt-files (whitespace,
register), supabase-migrations (probe-as-role, CAS patterns), connection-map.
`PLAN.md` + `SPEC-connection-map.md` — connection map. `SAGE_TODO.md` — the
older checklist; its Workstream D (plain-language mappings) is largely
absorbed by the trajectory brief.
