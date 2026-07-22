# Implementation-guidelines adoption notes (deliberate deviations)

Companion to `docs/sage-implementation-guidelines.html`. Every deviation from the
supervisor's document is listed here with its reason. Everything not listed is adopted
as written.

## 1. Server boundary: Flask on Vercel, not Supabase Edge Functions (RESOLVED)
The guidelines assume all server logic lives in Supabase Edge Functions. Our live
production backend is a Flask API on Vercel that satisfies every hard rule's intent
(client never calls third parties, keys server-side only, one safety choke point).
Asked 2026-07-21 (`docs/drafts/2026-07-21-supervisor-stack-email.md`);
**supervisor confirmed 2026-07-22 that Flask is fine** — the Flask boundary is
permanent, no edge-function port.

## 2. Safety classifier input: patient_name is NEVER sent to the LLM
The rules file's `classifier_contract.input` lists `patient_name`. Sending a patient
name to an external model would break the de-identification invariant (de-identify
before any external LLM call). The classifier LLM receives only the sanitized message
plus two non-identifying scalars (`on_active_treatment`, `perspective`). The
caregiver-voice `patient_line` ("Rosa needs a doctor now") is rendered SERVER-SIDE by
`render_patient_line()` after classification, so the product behavior the contract
wants is preserved without the name leaving our infrastructure.

## 3. "Log every non-NONE classification with the message" → database, not logs
Our no-PHI-in-logs rule forbids message text in console/function logs. The requirement
is satisfied by the `safety_classifications` TABLE (user-scoped, RLS, included in
delete_all_user_data — the same posture as `messages`); the console line carries only
tier/category/source/latency.

## 4. Classifier prompt carries a CONDENSED rules reference, not the full JSON
The guidelines say "with the JSON rules injected as reference data." The full trigger
lists tripled prompt size, exhausted Groq's TPM budget, and pushed latency into
timeout territory (measured 2026-07-21). The full trigger lists ARE enforced — 
deterministically, by the keyword floor that runs before every LLM call and can never
be lowered by it. The prompt keeps the tier definitions (full clinical content) plus
category names grouped by tier. The eval suite gates outcome accuracy.

## 5. Rules are the floor even when the floor is wrong-ish
A deterministic trigger hit can never be downgraded by the LLM (supervisor design:
"the rules are the floor"). Known cost: "is chest pain a common side effect of
oxaliplatin?" contains the literal trigger "chest pain" and escalates T1 even though
it is an informational question. This matches the PRE-EXISTING production behavior
(the legacy crisis short-circuit fired on the same phrase) and errs toward escalation.
Tracked as a promotion-loop candidate (e.g., a question-form co_modifier guard in a
future physician-reviewed rules version).

## 6. classifier model: Groq llama-3.3-70b-versatile (guidelines example: "a fast model is fine")
Bake-off 2026-07-21 on the tricky case set: Groq 70b-versatile 10/10 tiers at p50
0.6s; Together 70B-Turbo 10/10 at p50 2s; 8B/20B-class models mis-tiered; reasoning
models (gpt-oss) silently truncated or took 8-10s. Groq rate limits are per-model, so
the classifier rides the 70b bucket (12k TPM) separately from the 8B verifier. If the
weekly safety report shows a high `rules-fallback` rate (throttling), consider the
Groq paid tier or `MODEL_CLASSIFIER_PROVIDER=together`.

## 7. accounts split keeps patient_profiles keyed by user_id
The guidelines' `patient_profiles.account_id` and our `patient_profiles.user_id` hold
the same value (`auth.uid`). Renaming the key column would ripple through ~17 call
sites for zero behavior change; the `accounts` table is real, the FK relationship is
documented, the column name stays.
