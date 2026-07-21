# Sage Transition — Master To-Do

_Compiled 2026-07-18 from three sources: the supervisor email (2026-07-17), the product-flow
redesign (`docs/sage-product-flow.html`, v1 — 14 screens, 5 phases, wireframes + stack
notes), and meeting notes (2026-07-17). Decisions below were locked 2026-07-18.
UPDATED 2026-07-21: the supervisor's implementation guidelines
(`docs/sage-implementation-guidelines.html`) + safety rules
(`config/safety/sage-safety-rules-v0.9.json`) landed — see Workstreams S and I._

**Global standard (applies to every workstream):** no em dashes and sixth-grade reading
level in ALL patient-facing text — UI copy, backend-generated strings, AND AI output
(system prompt rule + an eval check, not just a copy sweep).

## Locked decisions
1. **Same repo, rebrand + evolve.** Backend brain stays live and untouched; mobile evolves
   in place. Rename the **existing** App Store Connect app (keeps bundle ID, TestFlight
   testers, build history).
2. **Chat model → `moonshotai/Kimi-K2.6` on Together** (final decision 2026-07-21,
   optimizing speed + performance on the API we have; supersedes the earlier
   `claude-sonnet-5` pick — the supervisor's email said "Claude API" generically, and
   the Anthropic path stays built + dormant: `MODEL_CHAT_PROVIDER=anthropic` +
   `ANTHROPIC_API_KEY` re-enables it with no deploy). Extractor (gpt-oss-120b) and
   Modeler (DeepSeek-V4-Pro) unchanged; emergency fallback upgraded to Groq
   `llama-3.3-70b-versatile`. One variable per eval window.
3. **Phone OTP auth now** — AMENDED 2026-07-21 per the implementation guidelines: the
   client talks ONLY to Supabase auth (`signInWithOtp`/`verifyOtp` via supabase-js);
   dashboard TEST phone numbers during dev, Twilio Verify at launch; the Flask
   `/api/auth/phone/*` proxy endpoints get deprecated (Workstream I). JWT /
   `require_auth` / RLS plumbing survives.
4. **First push: Onboarding + Home + Auth**, built INSIDE the current UI/UX template.
   The Sage doc's wireframes define **flow and content, not styling** — reuse theme
   tokens, Screen/Card/ListRow/Button primitives, drawer shell, one-line composer, chips.

## Section 0 — Keep-the-brain map (do NOT touch; all live in prod)
- Belief store + "is that right?" confirmation chips (== the doc's "extraction always
  confirmed" principle)
- Question policy: just-in-time, never-twice, register-matched (== doc principles 1–2)
- The Modeler: connections graph, scored expectations, calibration (not in the doc —
  our differentiator)
- Graph-aware trial ranking with plain-English rationale (exceeds doc Phase 5)
- 10-cancer guideline RAG (powers "ask about a term/report")
- De-identification pipeline, consent/MHMDA machinery, patient_events timeline,
  eval harness + test suites

## Workstream A — Rename → Sage (rides with the first push)
- [x] Mobile: app.json display name → Sage (KEEP bundle identifier; keep EAS
      slug/projectId internals so the EAS project isn't orphaned); all UI strings,
      drawer, welcome copy, HelpSheet header
- [ ] App Store Connect: rename the existing app record to Sage (display-name change
      only — testers + history preserved)
- [x] Web SPA branding sweep DONE; `mysage.chat` domain still open (DNS access → open question)
- [x] Backend patient-facing strings: chat lead-ins ("Here are clinical trials…"),
      just-in-time questions, confirmation prompts, trial warnings
- [x] Docs/README/HANDOFF naming sweep; entity footer "Wondrlink / Fwollo LLC" → confirm
      with supervisor before it appears anywhere patient-facing
- [ ] Em-dash + reading-level sweep extended to system prompts; add an eval check
      (assert no em dash in generated answers; flag >6th-grade vocabulary)

## Workstream B — FIRST PUSH: Onboarding + Home + Auth (doc Phases 1–2, screens 1–3c)
_Rule: current design system, new flow. No visual redesign._
- [x] **Phone OTP login** (screen 1): Supabase phone provider + Twilio Verify; "Text me
      a code"; no password, no email. Migration story for existing email pilot users
      (link phone to existing account or fresh start — decide with supervisor)
- [x] **Screen 2 — the branch**: "Who are you here for?" (Myself / A loved one) on its
      own uncluttered screen; sets `perspective` for everything downstream
- [x] **Screens 2a/2b — basics**: name, birth year, gender, location (caregiver variant
      adds their name + relationship + patient's name). Location = "use my location" tap
      OR free-text city/postal → store **lat/long + display name** (global from day one;
      backend already geocodes internally — ClinicalTrials.gov `filter.geo` takes lat/long
      directly, so this simplifies the trial path)
- [x] **Anchor question in chat** (screen 3): "what type of cancer?" asked conversationally
      — common-type chips + type-ahead accepting plain words ("stomach" → gastric);
      escape hatches: "We're still finding out" + caregiver path. Still-diagnosing →
      capability menu reorders (visit recording + explanations first, trials wait)
- [x] **Capability-menu home** (screen 3b): personalized menu ("Find clinical trials for
      breast cancer") + "or just talk to me" — permanent home after the anchor answer.
      Buttons inject chat openers (existing `?q=` handoff does exactly this)
- [x] **Data model NOW** (cheap now, painful later): account ≠ patient_profile split;
      account-level fields `account_holder_name`, `perspective` (self/caregiver),
      `relationship`, `patient_name`. Voice layer renders later (Workstream F)
- [x] Mic (voice input) in every composer row (doc callout: this audience speaks more
      easily than it types)

## Workstream C — Chat voice (registry-gated) — SHIPPED as Kimi-K2.6
- [x] Anthropic provider support in the `llm_utils` call path (built, DORMANT — env-var
      re-enable; `ANTHROPIC_API_KEY` not required)
- [x] Registry chat segment → **`moonshotai/Kimi-K2.6`** (Together). Kimi is a REASONING
      model: `try_together` gives it +1536 max_tokens headroom (reasoning consumes the
      budget before the visible answer) and sends
      `chat_template_kwargs={"enable_thinking": False}` (cuts latency ~4x: 27s → ~4s;
      shortens but does not fully remove the reasoning burst)
- [x] De-identification invariant unchanged (already provider-agnostic — runs before any
      provider sees text)
- [x] Eval gate on the swap (2026-07-21, colorectal `--suite all --mode llm`): NO
      regression vs the pre-swap baseline. keyword_compliance 80% PASS after widening
      one golden case to accept plain-language synonyms (Kimi says "numbness or
      tingling" instead of "neuropathy" — the sixth-grade voice we want).
- [ ] **Domain-gate follow-up (pre-existing, model-independent)**: symptom-described
      emergencies with no cancer keyword ("passing a lot of blood from my rectum",
      "12 bouts of diarrhea") are tier1-rejected → escalation missed
      (off_topic 88.89%/escalation 66.67%, identical before and after the swap).
      → FIX LANDS IN WORKSTREAM S: any non-NONE safety tier bypasses the domain gate.
- [ ] Sixth-grade + no-em-dash voice rules go into the system prompt as a SEPARATE
      follow-up eval window (Kimi currently emits em dashes)
- [ ] Modernize `scripts/test_all_features.py` keyword checks for the Sage voice
      (2026-07-21 run: 69/75; all 6 failures are literal-substring artifacts — "contact"
      vs "call" in the emergency template, "not giving up" tripping the `No 'giving up'`
      check, plain-language synonyms for wellbeing/colonoscopy — EXCEPT one real note:
      Kimi didn't proactively surface the diabetes-dexamethasone interaction on a generic
      FOLFOX side-effects question (direct diabetes question passes). Recheck proactive
      comorbidity surfacing in the voice-rules eval window.)

## Workstream S — Safety layer (supervisor mandate 2026-07-21; ONE eval window)
_Source: `docs/sage-implementation-guidelines.html` appendix + `config/safety/
sage-safety-rules-v0.9.json`. Classify-before-chat on EVERY inbound message; rules
loaded as DATA, never hardcoded in prompt strings. Plan: `.claude/plans/` (phases 1–6)._
- [ ] Rules loader + deterministic floor (`lib/safety_rules.py`; local-extensions file
      absorbs the legacy `_CRISIS_PATTERNS`; single keyword source)
- [ ] Classifier LLM (`classifier` registry segment, Groq 8b; `lib/safety_classifier.py`;
      floor always runs, LLM merges via tier_max, fail-open to floor on outage;
      kill switch `SAFETY_CLASSIFIER_ENABLED` default ON).
      PHI deviation (documented): patient_name NEVER sent to the LLM — caregiver
      patient_line renders server-side
- [ ] `safety_classifications` audit table (RLS, in delete_all_user_data) + weekly
      `scripts/safety_report.py` review ritual (rule_matched:false → promotion
      candidates for the next rules version)
- [ ] Wire into `/api/chat`: T1/T2/MH short-circuit card, T3 same-day banner alongside
      the normal reply, domain-gate bypass for non-NONE tiers, `POST /api/safety/
      log_symptom` (T2 "log this symptom" → patient_events)
- [ ] Client rendering: `EscalationCard` (mobile) + SPA in-thread card; shared types;
      T3 rides the existing UrgencyBanner channel
- [ ] Eval gate: `tier_accuracy` metric + `safety_classifier.yaml` suites; colorectal
      llm expects escalation_accuracy 66.67% → ~100%, ZERO under-escalations
- [ ] **LAUNCH BLOCKER: physician review of the rules file before real patients**
      (v0.9 is draft from NCI/ASCO materials; reviewer proposal: Dr. Csiki; promotion
      loop feeds v1.0)
- [ ] Emergency number is config (`EMERGENCY_NUMBER`, default 911) for later non-US launch

## Workstream I — Implementation-guidelines adoption (2026-07-21 doc)
- [ ] **Stack question SENT to supervisor 2026-07-21** (`docs/drafts/
      2026-07-21-supervisor-stack-email.md`): Flask boundary vs edge-function port.
      All work below is stack-portable either way. AWAITING ANSWER.
- [ ] Phone auth rework: mobile `sendPhoneCode`/`verifyPhoneCode` → direct
      `supabase.auth.signInWithOtp`/`verifyOtp`; deprecate then delete Flask
      `/api/auth/phone/*`; USER OPS: dashboard test numbers now, Twilio at launch
- [ ] `accounts` table split (id = auth.uid, holder_name, perspective, relationship;
      RLS own-rows; backfill from patient_profiles; patient_profiles stays user_id-keyed)
- [ ] RLS on every user-owned table (today only patient_events / consent_withdrawals /
      pattern_records have in-repo policies; core tables get enable+policy migrations —
      defense-in-depth; service-role backend unaffected)
- [ ] Gateway instrumentation: `lib/ai_gateway.py` `AI_CALL` log line {task, provider,
      model, latency_ms, tokens} across all 8 provider call sites (non-PHI scalars only)
- [ ] Prompts-as-files: every inline prompt constant → `lib/prompts/files/` (SHA-pinned
      pure relocation, NOT an eval variable)
- [ ] `sage-dev` Supabase project (scoped seed: schema + colorectal corpus) + Supabase
      CLI migration flow going forward; USER OPS: create project, enable phone provider

## Workstream D — Interview + report upload (doc Phases 4–5, screens 8–13)
- [ ] Structured, pausable, resumable interview triggered by trial matching (and any
      future story-dependent feature). Every answer saves instantly as a belief write —
      quitting halfway loses nothing and never blocks the rest of the app
- [ ] Plain-language mappings (the doc's table) onto EXISTING belief paths; "I'm not
      sure" always an option:
      - "Has the cancer spread?" → localized / regional / metastatic
      - "Which parts?" chips → metastasis sites (each opens/closes trial categories)
      - Treatments checklist + "did it come back or grow?" → prior lines (never say "lines")
      - "On most days, which sounds most like you?" (4 options) → ECOG 0–3
      - Comorbidity chips (heart, diabetes, hepatitis/HIV, autoimmune) → exclusions
- [ ] **Report/photo upload**: pathology + labs via camera/file → vision extraction
      (model pick 2026-07-21: `meta-llama/Llama-4-Maverick` on Together, new `vision`
      registry segment when built) →
      ALWAYS patient-confirmed through the existing pending-chips machinery ("Looks
      right" / "What does this mean?"). Never silently written. Biomarkers + labs are
      NOT asked as questions — reports do the hard part
- [ ] **Dual-language profile** (screen 13): "In your words" / "For your medical team"
      side by side — verification + vocabulary learning + a shareable document for the
      oncologist. A product feature in its own right
- [ ] Honest match framing: "trials that MAY fit," plain-words explanations on demand,
      "Questions for my doctor" button per trial card (final eligibility = care team)
- [ ] Staleness: gentle re-interview every few months; progression mentioned in any
      visit recap triggers the same refresh prompt

## Workstream E — Visit recorder (doc Phase 3, screens 4a–4c)
- [ ] Consent gate FIRST: one-tap "I've told my doctor I'm recording" + suggested script
      (recording-consent laws vary; asking aloud covers everywhere)
- [ ] Live streaming transcription (model pick 2026-07-21: `openai/whisper-large-v3`
      on Together, new `stt` registry segment when built; the existing text-based
      visit-recap pipeline seeds the summarizer)
- [ ] Three-part output, not a transcript: what the doctor said / what you do next /
      what to ask next time → saved permanently to the health log
- [ ] The one early just-in-time exception: proactively capture care-team name + office
      phone within the first days (it powers the safety card exactly when the patient
      can't think straight)

## Workstream F — Caregiver voice layer (doc "one app, two voices")
- [ ] Template variables through every patient-facing string (patient name, pronoun,
      relationship, perspective) + the same context in the AI system prompt — fourteen
      screens built once, rendered in two voices
- [ ] Caregiver-acknowledgment moments ("Caring for your mom is a lot"); the
      caregivers-answer-daily-life-more-accurately note as a moment of respect
- [ ] Workstream B's account/patient split makes this render-only

## Workstream G — Meeting-note features
- [ ] **Standard-of-care fallback**: when trial search yields nothing usable, present
      guideline-derived next-standard-of-care information (the RAG corpus already holds
      it) — the journey doesn't dead-end at "no trials found"
- [ ] **Push notifications** (local + server): general-care check-ins at intervals;
      pair with Modeler expectation windows so the "around cycle 4, how are your hands
      and feet?" check-in gets a delivery channel
- [ ] **Doctor's-note builder**: summarize changes/symptoms since the last appointment
      from the patient_events timeline (timeline + LLM + template — mostly free)
- [ ] **Local cache**: React Query persistence / offline reads for chat history +
      profile (hospital Wi-Fi reality)
- [x] ~~Safety upgrades from the doc~~ — SUPERSEDED by **Workstream S** (the supervisor
      shipped the red-flag list as `sage-safety-rules-v0.9.json`; escalation card +
      symptom logging land there; physician sign-off tracked as the launch blocker)

## Process / accountability (self-imposed)
- [ ] Per-build self-test checklist (smoke list run on every TestFlight build)
- [ ] Use the app weekly as if a patient — actual dogfooding, logged
- [ ] Each workstream lands with its eval/test additions (existing harness patterns)

## Open questions for the supervisor
- Fwollo LLC vs WondrLink Foundation — which entity/branding is canonical?
- `mysage.chat` DNS — who owns it, and when do we point it at the deployment?
- ~~Claude Sonnet API cost sign-off~~ — superseded 2026-07-21: chat runs on Together
  (Kimi-K2.6) with existing credits; Anthropic path dormant, no new spend to approve
- ~~Clinician-authored red-flag list~~ — received as `sage-safety-rules-v0.9.json`
  (2026-07-21); remaining ask = physician sign-off (Dr. Csiki?) → Workstream S blocker
- **Flask boundary vs edge-function port** — email sent 2026-07-21, awaiting answer
- Pilot recruiting timing vs. redesign landing — recruit now on the old UI or wait?
- Confirm: the pending old-WondrChat-UI TestFlight build is superseded and will NOT ship

## Suggested sequence
A+B+C SHIPPED → **S (safety layer, active now — supervisor's top structural ask)** →
I (guidelines adoption: auth, accounts, RLS, dev project, gateway discipline) → D
(interview + reports) → E (visit recorder) → F (caregiver voice) → G (notifications,
doctor's note, fallback, cache).
