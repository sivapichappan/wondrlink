# NIST AI RMF 1.0 Mapping — WondrChat

**Purpose:** Document the practices that satisfy each NIST AI Risk Management Framework function so we can claim the **Texas HB 149 (Responsible AI Governance Act, effective 2026-01-01) safe harbor** and have a coherent governance binder for any other regulator who asks.

**Status:** DRAFT — ATTORNEY REVIEW REQUIRED.
**Owner:** Engineering + Privacy Officer
**Last reviewed:** 2026-05-20

The NIST AI RMF organizes AI risk management into four functions: **Govern**, **Map**, **Measure**, **Manage**. This document enumerates the WondrChat practices that satisfy each, with cross-references to the actual files.

---

## Function 1 — GOVERN

> Cultivate a culture of risk management. Policies, processes, and procedures.

### GOVERN 1: Policies, processes, and procedures are in place

- **Privacy Policy** (`public/index.html` modal `privacyOverlay`) — covers data collection categories, sub-processor list, MHMDA + CCPA + 19-state rights, concrete retention periods (7-day delete + 90-day backup purge + 24-hour rate-limit + 6-year consent log + indefinite anonymous aggregates).
- **Consumer Health Data Privacy Notice** (`public/index.html` modal `consumerHealthOverlay`) — separate document per MHMDA § 4.
- **Terms of Use** (`public/index.html` modal `termsOverlay`) — eligibility (18+ verified by DOB picker), IL/NV state exclusion, EU/EEA/UK/Swiss geofence, no medical advice / not a Covered Entity.
- **Accessibility Statement** (`public/index.html` modal `accessibilityOverlay`) — WCAG 2.1 AA target, audit cadence, contact path.

### GOVERN 2: Accountability structures are in place

- **Incident Response Plan** ([docs/compliance/incident_response_plan.md](incident_response_plan.md)) — 60-day HBNR clock, severity matrix, five response phases, named role slots (IC / Privacy Officer / external counsel / on-call eng) pending appointment.
- **Tabletop scenarios** ([docs/compliance/irp_tabletop_scenarios.md](irp_tabletop_scenarios.md)) — three drillable scenarios with decision points.
- **Quarterly DPIA review cadence** ([docs/compliance/dpia.md](dpia.md)).
- **Monthly state-AI-law review cadence** ([docs/compliance/state_ai_law_tracker.md](state_ai_law_tracker.md)).
- **PR review template** requires clinical voice for any system-prompt or overlay change.

### GOVERN 3: Workforce roles + diversity are documented

- Role assignments documented in the Incident Response Plan with notes that specific people must be named in seat before launch (in-flight; tracked as a non-engineering blocker).

### GOVERN 4: Risk-management process is implemented

- **DPIA** ([docs/compliance/dpia.md](dpia.md)) — risk register, severity × likelihood matrix, mitigations.
- **Sub-processor chain** ([docs/compliance/subprocessor_chain.md](subprocessor_chain.md)) — vendor list, retention, DPA status, deletion flow.
- **EU geofence decision** ([docs/compliance/eu_geofence_decision.md](eu_geofence_decision.md)) — recorded as the conservative v1 posture with conditions to revisit.

### GOVERN 5: Mechanisms for stakeholder participation

- User feedback collected on every bot response (`api/index.py /api/feedback`) with feedback type + reason.
- Public contact paths: `info@`, `privacy@`, `appeals@`, `accessibility@` (aliases to be activated alongside the named role assignments).

### GOVERN 6: Lifecycle policies for procurement, use, deprecation

- Documented in the sub-processor chain; each renewal cycle triggers a review of retention / SCC / SOC 2 posture.

---

## Function 2 — MAP

> Contextualize AI risk. Understand the system, its inputs, its environment.

### MAP 1: Context is established and understood

- **System architecture:** SPA at `public/index.html` → Flask API at `api/index.py` → Supabase (auth, storage, RLS) + Together AI / Groq (LLM inference) + ClinicalTrials.gov (trials).
- **Sub-processor chain documented** with retention + DPA status.
- **Lawful basis documented** in the DPIA: Article 6(1)(b) contract + Article 9(2)(a) explicit consent.

### MAP 2: Categorization of the AI system

- **Application:** patient-facing health education for oncology patients.
- **Risk level:** limited risk under EU AI Act framing (transparency obligations only); not a regulated medical device under FDA CDS exemption framing (CDS-exemption memo pending counsel sign-off).
- **Not a Covered Entity under HIPAA** — no provider relationship; de-identification before LLM applied as defense-in-depth.

### MAP 3: AI capabilities, scope, intended use

- **In-scope:** education on diagnoses, treatment regimens, side-effect management, clinical-trial discovery, screening administration (PHQ-9, GAD-7, PSS-10, ISI as patient-administered tools), survivorship cadence, advance care planning prompts.
- **Out-of-scope:** therapy / psychotherapy (state-blocked in IL + NV), clinical decision support directing treatment, emergency response (we redirect to 988/911).

### MAP 4: Risks to individuals, groups, communities

- **Re-identification risk:** mitigated by aggressive de-identification + runtime PII guard (`detect_pii_leaks` in `lib/deidentify.py`).
- **Hallucination risk:** mitigated by RAG grounding + post-LLM validation + inline citations.
- **Unauthorized-practice-of-medicine risk:** mitigated by system-prompt language rules (`lib/prompts/base.py`), persistent disclaimers, per-session AI reminder, transcript red-team queued.
- **Crisis-response risk:** mitigated by `lib/confidence.py detect_crisis_pattern()` short-circuit (988, 741741, 911) with hardcoded responses that bypass the LLM entirely.

### MAP 5: Risks to legal compliance + reputation

- See **state_ai_law_tracker.md** — per-state obligation map.
- HBNR exposure documented in **incident_response_plan.md**.
- MHMDA private-right-of-action exposure mitigated via separate Consumer Health Data Privacy Notice + three opt-in consents + 45-day appeal SLA + withdraw-consent affordance.

---

## Function 3 — MEASURE

> Identify, measure, and analyze risks.

### MEASURE 1: Appropriate methods + metrics are identified

- **De-identification regression test** ([tests/test_deidentify.py](../../tests/test_deidentify.py)) — adversarial fixtures across SSN, phone, email, MRN, insurance ID, ZIP, ISO + US dates, street addresses. Runs in pytest.
- **Accessibility CI** ([.github/workflows/accessibility.yml](../../.github/workflows/accessibility.yml)) — axe-core via Playwright against critical flows; PRs blocked on `serious` or `critical` violations.
- **Per-cancer eval harness** ([scripts/eval/run_evals.py](../../scripts/eval/run_evals.py)) — runs 4 suites per cancer (golden, off_topic, cross_cutting, safety) against 6 metrics:
  - `off_topic_accuracy` (Tier 1 gate effectiveness)
  - `route_accuracy` (Tier 2 selected/general routing)
  - `retrieval_coverage` (RAG hit rate)
  - `citation_validity` (every cited source exists)
  - `escalation_accuracy` (crisis prompts trigger short-circuit)
  - `keyword_compliance` (system-prompt forbidden phrases never appear)

### MEASURE 2: AI systems are evaluated against documented criteria

- **Per-cancer eval baseline** captured per release. Current ready cancers: colorectal, breast, prostate, lung, melanoma, bladder, kidney, NHL, uterine, pancreatic — 10 of 10.
- Eval reports persisted as JSONL under `scripts/eval/reports/` with timestamps for trend analysis.

### MEASURE 3: Mechanisms for tracking + responding to risks

- **CSP Report-Only mode** in production ([vercel.json](../../vercel.json) + [api/index.py /api/csp-report](../../api/index.py)) — collects violation reports for 48 hours before flipping to enforced.
- **PII leak runtime guard** ([api/index.py](../../api/index.py) `detect_pii_leaks` call before LLM) — blocks + returns 500 + logs categories (never raw matches) on any pattern hit.
- **Logging:** structured logs via Python `logging`, no PHI in log output (codebase convention enforced via CLAUDE.md).

### MEASURE 4: Continuous improvement loop

- **Feedback collection on every bot response** (`/api/feedback`) — feeds into PR template for system-prompt tuning.
- **Per-cancer eval re-run on every prompt or overlay change** — established baseline + tolerance window for regressions.

---

## Function 4 — MANAGE

> Allocate resources to risks. Treat, monitor, communicate.

### MANAGE 1: Risks are prioritized + treated

- **Crisis short-circuit** ([lib/confidence.py](../../lib/confidence.py)) — highest-priority safety risk handled deterministically: ~60 keyword patterns covering self-harm, medical emergency, urgent oncology. Returns hardcoded 988 / 741741 / 911 responses; LLM never sees the query.
- **System-prompt language rules** ([lib/prompts/base.py](../../lib/prompts/base.py)) — forbidden phrases ("you should", "you must", "tell your doctor") with required replacements; post-response filter as belt-and-suspenders.
- **Rate limiting** ([lib/rate_limit.py](../../lib/rate_limit.py)) — Supabase-backed, per-endpoint per-identifier limits (3 register/min, 5 login/15min, 30 chat/min).
- **Withdraw-consent affordance** ([api/index.py /api/withdraw_consent](../../api/index.py)) — MHMDA-required separate affordance; chat is disabled when collection or sharing consent is withdrawn.

### MANAGE 2: Risk responses + adaptation

- **Persistent AI banner + per-session reminder** in chat — CA / UT / TN disclosure requirement.
- **State signup block** for IL + NV — UPM risk mitigation.
- **EU/EEA/UK/Swiss geofence** — GDPR + EU AI Act scope-limit until counsel + DPA chain are ready.
- **Age gate via DOB picker** — server-validated; we store age band, never the raw DOB.

### MANAGE 3: Risk monitoring + incident response

- **Incident Response Plan** ([docs/compliance/incident_response_plan.md](incident_response_plan.md)) — 60-day HBNR clock, severity matrix, escalation chain, notification templates pre-drafted.
- **Tabletop scenarios** ([docs/compliance/irp_tabletop_scenarios.md](irp_tabletop_scenarios.md)) — drillable.

### MANAGE 4: Risk communication + decommissioning

- **Sub-processor chain** documents which vendors hold what data + the deletion-cascade expectation.
- **Account deletion endpoint** (`/api/delete_account`) — deletes from all 8+ tables; vendor cascade via DPAs (pending signature).
- **Consent withdrawal log** retained 6 years as audit defense; the only data that survives an account deletion.

---

## TX HB 149 Safe Harbor Claim

Texas HB 149's safe harbor requires:

1. **Adoption** of a recognized AI governance framework. We adopt the NIST AI Risk Management Framework 1.0.
2. **Documentation** of the framework's application to our system. This document satisfies it.
3. **Ongoing review** cadence. Documented at:
   - DPIA: quarterly ([docs/compliance/dpia.md](dpia.md))
   - State law tracker: monthly ([docs/compliance/state_ai_law_tracker.md](state_ai_law_tracker.md))
   - Sub-processor chain: on each renewal cycle ([docs/compliance/subprocessor_chain.md](subprocessor_chain.md))
   - Incident Response Plan tabletop: annually before launch + after any significant change ([docs/compliance/irp_tabletop_scenarios.md](irp_tabletop_scenarios.md))

This document will be updated on the same monthly cadence as the state law tracker, with the decision log entry noted at the bottom.

---

## Decision log

- **2026-05-20** — Initial mapping. WondrChat claims the TX HB 149 NIST AI RMF safe harbor.
- _(future entries…)_

---

*Companion docs:* [DPIA](dpia.md) · [Incident Response Plan](incident_response_plan.md) · [Tabletop Scenarios](irp_tabletop_scenarios.md) · [Sub-processor Chain](subprocessor_chain.md) · [State AI Law Tracker](state_ai_law_tracker.md) · [EU Geofence Decision](eu_geofence_decision.md)
