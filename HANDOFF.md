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

**Decisions this leaves the owner:**
- Sage currently speaks with the PRE-Kimi voice. Options: pay for a Together
  dedicated Kimi-K2.6 endpoint, pick a new serverless voice (own eval window),
  or keep the rollback. Note `gpt-oss-120b` was tried as classifier first and
  REJECTED: reasoning burn + it missed fever-on-treatment (under-escalation).
- The verifier (`gpt-oss-20b`) shipped unvalidated (it fails open harmlessly);
  worth a spot-check. Glossary on `gpt-oss-120b` likewise unvalidated.
- Any llm-mode eval baseline from the Kimi era is now cross-model — do not
  compare numbers across 2026-08-24 without noting the voice change.

## RESUME HERE — changes 1 + 2 BUILT; change 3 is next (home-as-chat)

**Change 2 (kill the builder) is DONE** (dd29639 + 0012266): build.tsx
(1,014 lines) deleted with every entry point retargeted at scan/chat; the
first-launch setup modal deleted; the trials just-in-time ask is rule-6 /
screen-09 copy end to end (validate_trial_search_readiness + offer_scan +
the Scan-a-report / Just-tell-me / Not-now options on the trials screen).
The conversational machinery it relies on already existed (question_policy
asks stage + ZIP; extraction + scanner fill the profile).

**Change 3 part 1 (design-system pivot) is DONE** (9ff441a): mockup tokens
live in mobile/constants/theme.ts (paper ground, sage actions, ink text,
warm patient bubble), Source Serif 4 + Instrument Sans loaded, Sage's chat
prose is serif 16/25, patient bubbles are the one warm element. JS-only.

**Change 3 remainder (NEXT): home becomes the conversation** — home route
renders chat with the Sage wordmark + italic stage-words header; composer
"+" sheet with exactly three rows (Scan a report / Record a visit / Since
your last visit); dealt-card mechanism (sage accent border) with
engagement instrumentation from day one (the brief's stated risk: if cards
underperform, scanning starves and trials never unlock) — v1 cards: the
wall doctor-questions card, the trials ask, the scan suggestion; then the
nine-tool grid dies. Then changes 4 (check-ins in chat) and 5 (onboarding).

**Review debt:** changes 2 + retheme have NOT had the adversarial review
pass (subagent session limit until ~5:50pm ET 2026-08-24); run it before
the cohesive push, together with change 3's.

**Owner decision on record: NO push until all five changes land as one
cohesive update.** Ten local commits and counting on main.

### Change 1 record — gate inversion (BUILT, reviewed, validated)

Spec is in `docs/redesign/` (brief v1.1 + mockups; the `:root` block is the
token source of truth; mockup copy is canonical). Change 1 was adversarially
reviewed (28 confirmed findings, all fixed) and validated: 1077 offline
tests; dry + llm engagement evals 19/19 wall_accuracy; real llm answers make
the three-part move with the verbatim limit sentence.

What shipped in change 1:
- `lib/walls.py` — deterministic wall detection (prognosis/diagnosis/dosing;
  crisis stays frozen and always outranks). Direct personal-prognosis asks →
  the fixed screen-12 card (tier NONE + no detected urgency only). All other
  wall contact → LLM with the wall rule appended LAST + `enforce_wall()`
  guaranteeing the fixed limit sentence in code. Patterns are clause-anchored
  ("how long do I have TO WAIT" is logistics, never the card).
- Off-topic refusal deleted from `/api/chat` + sandbox mirror; deep research
  keeps its old gate pending the change-3 tool decision.
- `chat_base.md` re-pinned: walls + default-engage rules; STAGE_PROGNOSIS
  injection deleted (rule 5 + it was colorectal-only leak); pancreatic
  overlay reworded.
- Evals: `off_topic.yaml` → `engagement.yaml` (×10 cancers), new
  deterministic `wall_accuracy` metric (threshold 1.00, dry-mode-real),
  harness re-mirrored; `ChatWall` in shared/types.ts + mobile whitelist
  (client change is JS-only → OTA when pushed).

### The remaining changes, in order

2. **Kill the 6-step builder.** Learn from scans + conversation; every data
   request says why, names exactly what is missing, offers an escape hatch;
   trials unlock "when Sage knows enough."
3. **Home becomes the conversation.** "+" holds exactly three tools (Scan a
   report / Record a visit / Since your last visit); everything else arrives
   as dealt cards in-stream. Instrument card engagement from day one — if
   cards underperform, scanning starves and trials never unlock.
4. **Check-ins become 2–3 engine-chosen plain questions in chat** (from the
   patient's regimen). The six questionnaires die, including PREMM5 — a named,
   accepted cost.
5. **Onboarding shrinks to 3 screens + a conversation.** Welcome (oncologist
   = footer link) → one legal screen (DOB once, state, three frozen
   checkboxes) → "Who are you here for?" → chat asks the rest.

Below the top five: the "Since your last visit" compiler (confirmed facts
only), the allowlisted ingestion pipeline (NCI/ACS/NCCN-patient/MedlinePlus,
diff-and-re-review; the refusal log is the monthly acquisition list),
appointment-date awareness in the patient model.

### Cross-cutting

- The 9 communication rules (memory `project_trajectory_pivot` has them
  compressed; the brief is authoritative). Rule 1 = sixth-grade readability
  enforced in CI, not review-time taste.
- **Full retheme**: `mobile/constants/theme.ts` moves to the mockup tokens —
  paper `#F6F7F3`, sage `#4A7862`, warm `#F1E9DC` reserved for the patient's
  own bubbles; Source Serif 4 = Sage's voice, Instrument Sans = interface.
  Typography is semantic: it tells the patient who is speaking.
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
