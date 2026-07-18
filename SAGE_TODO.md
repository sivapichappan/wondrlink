# Sage Transition — Master To-Do

_Compiled 2026-07-18 from three sources: the supervisor email (2026-07-17), the product-flow
redesign (`docs/sage-product-flow.html`, v1 — 14 screens, 5 phases, wireframes + stack
notes), and meeting notes (2026-07-17). Decisions below were locked 2026-07-18._

**Global standard (applies to every workstream):** no em dashes and sixth-grade reading
level in ALL patient-facing text — UI copy, backend-generated strings, AND AI output
(system prompt rule + an eval check, not just a copy sweep).

## Locked decisions
1. **Same repo, rebrand + evolve.** Backend brain stays live and untouched; mobile evolves
   in place. Rename the **existing** App Store Connect app (keeps bundle ID, TestFlight
   testers, build history).
2. **Chat model → `claude-sonnet-5`** (latest Claude Sonnet) via the model registry.
   Extractor/Modeler segments unchanged. Full eval battery on the swap; one variable per
   eval window.
3. **Phone OTP auth now** (Supabase phone provider + Twilio) — auth-method swap; JWT /
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
- [ ] Mobile: app.json display name → Sage (KEEP bundle identifier; keep EAS
      slug/projectId internals so the EAS project isn't orphaned); all UI strings,
      drawer, welcome copy, HelpSheet header
- [ ] App Store Connect: rename the existing app record to Sage (display-name change
      only — testers + history preserved)
- [ ] Web SPA branding sweep; `mysage.chat` domain (DNS access → open question)
- [ ] Backend patient-facing strings: chat lead-ins ("Here are clinical trials…"),
      just-in-time questions, confirmation prompts, trial warnings
- [ ] Docs/README/HANDOFF naming sweep; entity footer "Wondrlink / Fwollo LLC" → confirm
      with supervisor before it appears anywhere patient-facing
- [ ] Em-dash + reading-level sweep extended to system prompts; add an eval check
      (assert no em dash in generated answers; flag >6th-grade vocabulary)

## Workstream B — FIRST PUSH: Onboarding + Home + Auth (doc Phases 1–2, screens 1–3c)
_Rule: current design system, new flow. No visual redesign._
- [ ] **Phone OTP login** (screen 1): Supabase phone provider + Twilio Verify; "Text me
      a code"; no password, no email. Migration story for existing email pilot users
      (link phone to existing account or fresh start — decide with supervisor)
- [ ] **Screen 2 — the branch**: "Who are you here for?" (Myself / A loved one) on its
      own uncluttered screen; sets `perspective` for everything downstream
- [ ] **Screens 2a/2b — basics**: name, birth year, gender, location (caregiver variant
      adds their name + relationship + patient's name). Location = "use my location" tap
      OR free-text city/postal → store **lat/long + display name** (global from day one;
      backend already geocodes internally — ClinicalTrials.gov `filter.geo` takes lat/long
      directly, so this simplifies the trial path)
- [ ] **Anchor question in chat** (screen 3): "what type of cancer?" asked conversationally
      — common-type chips + type-ahead accepting plain words ("stomach" → gastric);
      escape hatches: "We're still finding out" + caregiver path. Still-diagnosing →
      capability menu reorders (visit recording + explanations first, trials wait)
- [ ] **Capability-menu home** (screen 3b): personalized menu ("Find clinical trials for
      breast cancer") + "or just talk to me" — permanent home after the anchor answer.
      Buttons inject chat openers (existing `?q=` handoff does exactly this)
- [ ] **Data model NOW** (cheap now, painful later): account ≠ patient_profile split;
      account-level fields `account_holder_name`, `perspective` (self/caregiver),
      `relationship`, `patient_name`. Voice layer renders later (Workstream F)
- [ ] Mic (voice input) in every composer row (doc callout: this audience speaks more
      easily than it types)

## Workstream C — Chat = Claude Sonnet (parallel; registry-gated)
- [ ] Anthropic provider support in the `llm_utils` call path; registry chat segment →
      **`claude-sonnet-5`**; `ANTHROPIC_API_KEY` in the Vercel team project
- [ ] De-identification invariant unchanged (already provider-agnostic — runs before any
      provider sees text)
- [ ] Full eval battery on the swap ONLY (no prompt changes in the same window); capture
      a cost readout for the supervisor
- [ ] Sixth-grade + no-em-dash voice rules go into the system prompt as a SEPARATE
      follow-up eval window after the model swap passes

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
- [ ] **Report/photo upload**: pathology + labs via camera/file → vision extraction →
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
- [ ] Live streaming transcription (evaluate streaming STT; the existing text-based
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
- [ ] **Safety upgrades from the doc**: escalation card with big "Call my care team" /
      "Call 911" buttons; red-flag symptom list AUTHORED BY A CLINICIAN (request from
      Dr. Csiki — fever on treatment, uncontrolled bleeding, sudden confusion, chest
      pain, suicidal distress → warm human resources); then the one useful non-medical
      action (log the symptom with a timestamp)

## Process / accountability (self-imposed)
- [ ] Per-build self-test checklist (smoke list run on every TestFlight build)
- [ ] Use the app weekly as if a patient — actual dogfooding, logged
- [ ] Each workstream lands with its eval/test additions (existing harness patterns)

## Open questions for the supervisor
- Fwollo LLC vs WondrLink Foundation — which entity/branding is canonical?
- `mysage.chat` DNS — who owns it, and when do we point it at the deployment?
- Claude Sonnet API cost sign-off (bring the eval + cost readout from Workstream C)
- Clinician-authored red-flag list (Workstream G safety card)
- Pilot recruiting timing vs. redesign landing — recruit now on the old UI or wait?
- Confirm: the pending old-WondrChat-UI TestFlight build is superseded and will NOT ship

## Suggested sequence
A+B together (rename + new entry flow) → C in parallel (model swap is registry + evals)
→ D (interview + reports; biggest capability jump on our strongest backend) → E (visit
recorder) → F (caregiver voice) → G (notifications, doctor's note, fallback, cache)
— with the safety-card upgrade slotted as soon as Dr. Csiki's red-flag list arrives.
