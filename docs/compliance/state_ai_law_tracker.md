# State AI Law Tracker

**Status:** ACTIVE, monthly review cadence during 2026
**Code source of truth:** [lib/compliance.py `STATE_REQUIREMENTS`](../../lib/compliance.py)
**Owner:** Engineering + Privacy Officer

> ⚠️ **DRAFT — ATTORNEY REVIEW REQUIRED.** This tracker is the engineering-side mirror of the structured config in `lib/compliance.py`. Counsel ratifies what we owe to whom; this document records what we've done about it.

This is the human-readable companion to `STATE_REQUIREMENTS` in `lib/compliance.py`. Both must stay in sync. When a new state law lands:

1. Add or update the entry in `STATE_REQUIREMENTS`.
2. Add the row to this tracker with the citation + effective date + monitoring notes.
3. If the law adds a new obligation type that isn't already in the schema (`block_signup`, `require_ai_disclosure`, `mhmda_consent`, `safe_harbor`), extend the schema first.

## Obligation types

| Key | Meaning | Mechanism |
|---|---|---|
| `block_signup` | Refuse signup from this state | `lib/compliance.py validate_state()` returns 422; frontend renders the state-restricted modal |
| `require_ai_disclosure` | Persistent AI banner + per-session reminder | Persistent banner in `public/index.html` + `SESSION_META_HTML` injection (Task 3). Active for all users, regardless of state. |
| `mhmda_consent` | Three-checkbox MHMDA consent flow | Universal in our signup (Task 4). Active for all users. |
| `safe_harbor` | Claim a recognized AI governance framework | Documented mapping at [docs/compliance/nist_ai_rmf_mapping.md](nist_ai_rmf_mapping.md) (Task 12) |

## Active state laws

| State | Law | Effective | Obligations | How we comply | Last reviewed |
|---|---|---|---|---|---|
| **IL** | WOPR Act | 2025-08-04 | block_signup | Signup blocked + state-restricted modal | 2026-05-20 |
| **NV** | AB 406 | 2025-07-01 | block_signup | Signup blocked + state-restricted modal | 2026-05-20 |
| **CA** | AB 3030 / SB 1120 + 2026 chatbot law | 2026-01-01 | require_ai_disclosure | Persistent banner + session reminder + AI-bot avatar with `aria-label="WondrLink"` | 2026-05-20 |
| **UT** | HB 452 (Mental Health Chatbot Act) | 2025-05-07 | require_ai_disclosure | Same as CA | 2026-05-20 |
| **TN** | TN AI chatbot disclosure law | 2026-07-01 | require_ai_disclosure | Same as CA (effective ahead of statute) | 2026-05-20 |
| **TX** | HB 149 (Responsible AI Governance Act) | 2026-01-01 | safe_harbor (NIST AI RMF) | NIST AI RMF mapping doc (Task 12) | 2026-05-20 |
| **WA** | My Health My Data Act (MHMDA) | 2024-03-31 | mhmda_consent + separate notice + 45-day appeal SLA | Separate Consumer Health Data Privacy Notice + three-checkbox consent (Task 4) + appeal form | 2026-05-20 |

## On the watch list (not yet enacted or pending engrossment)

These bills are currently moving through state legislatures or were recently enacted but have effective dates we're past. Track these monthly during 2026.

- **FL** — multiple AI bills in committee, none currently impose direct obligations on patient-facing chatbots
- **MA** — AI bills targeting healthcare AI under committee review
- **NH** — AI transparency bill in committee
- **NY** — multiple AI-in-healthcare bills, several with disclosure obligations similar to CA/UT
- **OH** — AI bills in committee
- **PA** — UPM (Unauthorized Practice of Medicine) action vs Character.AI (May 2026) is the leading-case precedent
- **NJ** — AI bills in committee
- **NC** — AI bills in committee

When a watch-list bill is signed:
1. Read the text.
2. Map to one or more obligation keys above (or define a new one).
3. Add the row to "Active state laws" + update `STATE_REQUIREMENTS`.
4. Decide on enforcement timing (immediately on effective date, vs. earlier as defensive posture).

## Federal + non-state items we monitor in parallel

These don't fit the state-by-state map but are tracked here for visibility because they touch the same product surfaces.

- **FTC Health Breach Notification Rule (HBNR)** — applies to all users. See [docs/compliance/incident_response_plan.md](incident_response_plan.md).
- **FDA SaMD / CDS exemption** — CDS-exemption position memo pending counsel.
- **EU AI Act** — geofenced out for v1; see [docs/compliance/eu_geofence_decision.md](eu_geofence_decision.md).
- **CCPA / CPRA Limit Use of SPI** — universal affordance (Task 7).

## Monthly review checklist

Run this on the first business day of each month during 2026:

1. Check the trackers (HealthIT.gov AI policy roundup; IAPP state tracker; NCSL AI legislation tracker).
2. Cross-reference any new bills against the watch list above.
3. Re-read each "Active state laws" row — has the law been amended?
4. Update "Last reviewed" dates in this doc.
5. If anything changed substantively, ping counsel via privacy@wondrlinkfoundation.org.

## Decision log

- **2026-05-20** — IL + NV initial block; WA MHMDA consent flow shipped; CA/UT/TN AI disclosure satisfied via universal persistent banner + per-session reminder; TX HB 149 safe harbor claimed via NIST AI RMF mapping.
- _(future entries…)_

---

*Companion docs:* [DPIA](dpia.md) · [Incident Response Plan](incident_response_plan.md) · [Sub-processor Chain](subprocessor_chain.md) · [NIST AI RMF mapping](nist_ai_rmf_mapping.md) · [EU geofence decision](eu_geofence_decision.md)
