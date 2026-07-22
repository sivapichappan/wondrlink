# HANDOFF — active work

_Keep this for in-flight work only. Fold anything permanent into `.claude/CLAUDE.md`
and prune the rest. Last updated: 2026-07-22._

## NEW: Safety layer (Workstream S) — SHIPPED + LIVE 2026-07-22

The supervisor's implementation guidelines + `sage-safety-rules-v0.9.json` landed
2026-07-21 and the full classify-before-chat safety layer shipped the next day
(commits `66ae6c0`→`ce9fb32`, all pushed + deployed): tiered T1/T2/MH escalation
cards / T3 banner, deterministic keyword floor + Groq-70B judgment layer (concurrent
with retrieval, raise-only merge, fail-open), `safety_classifications` audit table,
weekly `scripts/safety_report.py`, eval gate PASSED (tier_accuracy 100%,
escalation_accuracy 66.67%→100% — the old domain-gate safety misses are FIXED).
Also shipped from the guidelines: AI_CALL telemetry on all 9 LLM call sites,
prompts-as-files (SHA-pinned), direct supabase-js phone OTP (Flask endpoints
deprecated), accounts table split (applied to prod, 5/5 backfilled), sage-dev
project created (`eizhshntrquvqwfsseeh`; bring-up steps in
`supabase_migrations/README.md`).

**CRITICAL FIX riding along:** `.vercelignore`'s blanket `*.md` had been silently
excluding `config/cancers/*/overlay.md` from every deploy — prod chat was running
the GENERIC overlay stub, not the per-cancer prompts the evals validate. Fixed with
negation patterns; `/api/health` now reports `prompt_files: 10, overlays: 10`.

**Open on the safety layer:** physician review of the rules file = LAUNCH BLOCKER
(Dr. Csiki proposed). Stack question RESOLVED 2026-07-22: supervisor confirmed
Flask stays — no edge-function port. Deviations documented in
`docs/sage-implementation-guidelines-notes.md`.

## Sage transition — Workstreams A+B+C SHIPPED; the one in-flight step is the iOS build

The product is **Sage** (renamed from WondrChat, supervisor meeting 2026-07-17). The
full checklist, locked decisions, and follow-ups live in **`SAGE_TODO.md`** — start
there. Backend is live on `wondrchat.vercel.app` with everything below deployed:

- **A — rename** (`1c8f8b0`): mobile + web SPA + backend strings → Sage; identifiers
  (bundle ID, EAS slug, apiBase, storage keys, table names) untouched.
- **B — onboarding/home/auth** (`1c8f8b0`, `8ac9cc2`): phone-OTP endpoints
  (`/api/auth/phone/send|verify`), account-basics API + `needs_basics` gate,
  who-for/basics screens, anchor-question home, capability menu. Migration
  `2026_07_18_sage_account_fields.sql` applied to prod.
- **C — chat voice** (`007926c`, `86971ff`): chat = **Kimi-K2.6 on Together**
  (final decision 2026-07-21; supersedes claude-sonnet-5 — Anthropic path built but
  DORMANT behind `MODEL_CHAT_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`). Fallback
  upgraded to Groq `llama-3.3-70b-versatile`. Eval gate passed: no regression vs
  pre-swap baseline; all-10 dry sweep PASS; latency ~4s after reasoning suppression.

**USER OPS before the build ships end-to-end:**
1. Supabase dashboard → Authentication → Phone provider: add TEST phone numbers
   (e.g. `+15550001111 = 123456` + your real numbers) — phone login then works
   with NO SMS provider. Twilio Verify at launch, same dashboard setting.
   Do the same on sage-dev.
2. Rename the existing App Store Connect app record to Sage (display name only).
3. `cd mobile && eas build --platform ios --profile production` → upload via
   Transporter (`eas submit` blocked) → commit the `app.json` buildNumber bump.
   This build now also ships the EscalationCard + direct supabase-js phone OTP.
4. Optional: `ANTHROPIC_API_KEY` only if the Claude voice is ever wanted.
5. sage-dev bring-up (needs prod DB password): `supabase_migrations/README.md`.

On-device smoke after the build: phone/email login → consent → who-for → basics →
anchor question (chips + "We're still finding out") → capability menu → chat;
drawer/Recents; crisis modal on every send path; trials Matches/Saved.

## Next follow-up eval windows (one variable each — order per SAGE_TODO)
1. **Voice rules into the system prompt** (no em dashes + sixth-grade language — Kimi
   currently emits em dashes); recheck proactive comorbidity surfacing in the same look.
   NOTE: prompt changes now also require bumping the SHA pin in
   `tests/test_prompt_relocation.py` (deliberate-change guard).
2. ~~Tier-1 domain-gate safety fix~~ — DONE 2026-07-22 via the safety layer
   (escalation_accuracy 100%).
3. Modernize `scripts/test_all_features.py` literal-substring checks for the Sage voice
   (6 known artifacts, detailed in SAGE_TODO Workstream C).

## Then: Workstream D (interview + report upload)
Biggest capability jump; model picks locked: vision = `meta-llama/Llama-4-Maverick`,
new `vision` registry segment. Workstream E STT pick: `openai/whisper-large-v3`.

## Standing operations
- Weekly `python3 scripts/modeler_report.py --all` → forward to Dr. Csiki (monitoring).
- Weekly `python3 scripts/safety_report.py` → review AI-judgment escalations
  (`rule_matched: false`) + rules-fallback share; promotion candidates feed the next
  physician-reviewed rules version.
- All lifecycle flags live in prod since 2026-07-14 (beliefs write + Modeler + graph
  trial ranking); rollback for any layer = unset its flag.

## Open follow-ups (not started, still valid)
- Learning-loop activation — attorney checklist in
  `docs/compliance/model_improvement_dormant.md`.
- Web SPA parity — softened nudges/wizard copy on web still form-first; web ignores
  `pending_confirmations` (chips are mobile-only, no breakage).
- Retire `chat_messages` double-write + legacy `/api/save_message`/`/api/chat_history`
  once old app builds age out.
- Delete the dead duplicate Vercel project (`wondrchat` in the personal scope /
  `wondrchat-nine.vercel.app`) to prevent wrong-project deploys.
- Consent-management UI: verify withdraw/restore end-to-end (prod has
  `consent_withdrawals` since 2026-07-14).
