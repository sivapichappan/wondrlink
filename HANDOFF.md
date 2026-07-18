# HANDOFF — active work

_Keep this for in-flight work only. Fold anything permanent into `.claude/CLAUDE.md`
and prune the rest. Last updated: 2026-07-18._

## PIVOT: WondrChat → Sage (supervisor meeting 2026-07-17) — THE active work

The product is being renamed **Sage** with a flow redesign per the supervisor's doc
(`docs/sage-product-flow.html` — 14 screens, 5 phases). **The full checklist, locked
decisions, and sequencing live in `SAGE_TODO.md` (repo root) — start there.**
Locked 2026-07-18: same repo rebrand+evolve (backend brain untouched, still live);
rename the EXISTING App Store Connect app; chat model → `claude-sonnet-5` via the
registry (evals gate); phone-OTP auth now; first push = onboarding+home+auth built
inside the CURRENT design system (doc wireframes = flow/content, not styling).
Global standard: no em dashes + sixth-grade language in ALL patient-facing text incl.
AI output.

**SUPERSEDED: the pending old-WondrChat-UI eas build should NOT ship** (was: nav
overhaul + lifecycle chips + trial reasons build). Those features ship inside the Sage
first push instead. Confirm with supervisor (open question in SAGE_TODO.md).

## Push 3: Model-driven trial matching — SHIPPED + LIVE (2026-07-14 night)

Commits `37e615d`→`cd6f140`, deployed. Trial ranking now consumes the connections graph
when `modeler_active()` (TRUE): contraindication demotions (−25/−15 × strength, capped
−30, warning always FIRST for mobile), supports_therapy boosts (+15/+8, capped +20),
toxicity-history warnings (score-neutral by design), completed-regimen warnings,
bidirectional `DRUG_CLASS_SYNONYMS` matching (word-boundary only). Verified pre-push
against real prod graphs + live ClinicalTrials.gov (pembro patient: warning w/ zero
score change; +6 boosts recorded). Telemetry live: `trials_shown` (excluded from Modeler
timeline/debounce via `_EXCLUDED_EVENT_KINDS`) + `POST /api/trials/feedback` →
`trial_feedback` (Modeler-ingested). Evals: `trials_ranking` suite 5/5 @1.00; pytest
79/79. Mobile (rides the eas build): match-reasons row on TrialCard + save/remove
feedback pings. Follow-ups logged in the plan: weight learning from feedback outcomes,
ECOG/comorbidity vs sectioned eligibility text, synonyms→config, server-side watchlist.
**The 3-phase product vision is now fully implemented end-to-end.**

## Push 2: Modeler / connections layer — FULLY LIVE (user skipped the bake, 2026-07-14)

All code phases committed + pushed (`13a03d1`→`ee3e7da`); **user decision 2026-07-14
evening: skip both bake periods — `FEATURE_BELIEFS_WRITE`, `FEATURE_MODELER`, AND
`FEATURE_MODELER_ACTIVE` are ALL `true` in production.** The belief store is the live
writer, the Modeler runs (client trigger + nightly cron `0 7 * * *` UTC), and all three
consumers are active. Runbook: `docs/modeler.md`.
- Go-live verified end-to-end: graphs force-seeded for all 5 patients (20 edges — 3
  corroborated, e.g. pembrolizumab→fatigue 0.83 — 7 expectations, 12 reflections,
  **2 pending confirmation chips queued**); live cron run: 5 candidates / 5 debounce-skips /
  0 errors. Seed pass surfaced + fixed two V4-Pro parsing failure modes (truncation at
  2500 tokens, markdown fences) — hardened in `ee3e7da`.
- **Dr. Csiki reports are now MONITORING, not gating**: run
  `python3 scripts/modeler_report.py --all` weekly and forward (first batch generated
  2026-07-14, in `scripts/eval/reports/modeler/`).
- Watch in week one: pending-queue crowding (reflections share cap 3 with extraction),
  `exp:` topic share of `question_asked` events, `modeler_run` reject/error rates,
  calibration accrual (hit-rate becomes meaningful after ~10 resolutions).
- Rollback for any layer = unset its flag (consumers vanish next request; graphs keep).
- Known gap: chips render only on mobile (Phase 6 UI) — the web SPA ignores
  `pending_confirmations`; web users simply never see the chips (no breakage).

## The one in-flight step: the iOS build

Everything else is SHIPPED and verified (backend live on `wondrchat.vercel.app`, all
migrations applied, beliefs backfilled, shadow extraction recording). One
`eas build --platform ios --profile production` → Transporter ships FOUR bodies of committed
mobile work at once:
1. Nav overhaul — assistant-home + drawer, multi-conversation chat (`/chat/[id]`, Recents, search)
2. Design-system polish (Screen/Card/ListRow primitives, FontSize scale, 20px gutter)
3. R2 refinements — one-line "Let's talk" composer, decluttered top bar, swipe gestures, no em dashes
4. Lifecycle UI — "is that right?" confirmation chips, stage cue, softened onboarding, trials just-in-time question

After the build: commit the `mobile/app.json` buildNumber bump. On-device smoke: drawer
(button + swipe-open + drag-close), new chat creates/titles/persists across relaunch, Recents,
crisis modal on every send path, trials Matches/Saved + "One quick question" → prefilled composer.

## Scheduled: the belief-write flip (~2026-07-21)

Shadow bake started **2026-07-14** (`FEATURE_EXTRACTION_SHADOW=true` live). After ~1 week:
run `python3 scripts/compare_shadow_extraction.py`, review high-stakes/negation stats, and if
clean set `FEATURE_BELIEFS_WRITE=true` in Vercel (team project) — extraction v2 becomes the
writer and confirmation chips go live. Gold evals already green (extraction 100/92/100;
policy 100). Flag rules + deploy truths: `.claude/CLAUDE.md` + [memory] infra_vercel_deploy.

## Open follow-ups (not started)
- **Modeler / connections layer** — next major push; consumes `patient_events`;
  `MODEL_MODELER` (DeepSeek-V4-Pro) reserved; needs vercel `crons` or client-trigger.
- **Model-driven trial scoring** — blocked on the Modeler.
- **Kimi-K2.6 chat swap** — env flip + full eval battery per `docs/model_registry.md`.
- **Learning-loop activation** — attorney review checklist in
  `docs/compliance/model_improvement_dormant.md` (consent copy → version bump → opt-in UI → flag).
- **Web SPA parity** — softened nudges/wizard copy on web still form-first (server changes shared).
- **Retire `chat_messages` double-write** + legacy `/api/save_message`/`/api/chat_history`
  once old app builds age out.
- **Delete the dead duplicate Vercel project** (`wondrchat` in the personal scope /
  `wondrchat-nine.vercel.app`) to prevent wrong-project deploys.
- Consent-management UI: verify withdraw/restore works end-to-end now that
  `consent_withdrawals` exists in prod (it was missing until 2026-07-14).
- 3 pre-existing LLM keyword flakes in `test_all_features.py` (items 1, 12, Emergency regression).
