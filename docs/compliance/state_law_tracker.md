# WondrLink — State Law Tracker

> **DRAFT — INTERNAL USE — LIVING DOCUMENT.**
> Reviewed quarterly during the compliance review cadence. Last update: May 2026.

## Purpose

Track US state AI / healthcare / privacy legislation that affects WondrLink's posture, so that signup gating, consent flows, and policy text stay in line with current law. Maintained by the Privacy Officer.

## Posture Codes

- **Blocked** — WondrLink does not serve residents of this state at signup.
- **MHMDA-compliant** — Served, with the separate Consumer Health Data Privacy Notice and three distinct opt-in consents.
- **Standard** — Served under the default consent flow (which is MHMDA-compliant globally to simplify the UX).
- **Monitor** — No action required; tracking enacted/pending laws that may affect us later.

## Active Restrictions and Compliance Requirements

| State | Law | Effective | Posture | Notes |
|---|---|---|---|---|
| WA | My Health My Data Act (RCW 19.373) | Mar 2024 | MHMDA-compliant | Separate Consumer Health Data Privacy Notice required; three distinct opt-in consents required; 45-day SLA for rights requests; private right of action with treble damages up to $25k. |
| IL | WOPR Act (PA 103-1131) | Aug 4, 2025 | Blocked at signup | Prohibits AI-delivered "therapy or psychotherapy" without a licensed professional. WondrLink's screeners + response generation could be argued in scope; not currently serving IL residents. |
| NV | AB 406 | Jul 1, 2025 | Blocked at signup | Prohibits AI mental/behavioral health services that constitute professional practice. Same reasoning as IL. |
| UT | HB 452 | May 7, 2025 | Standard with AI disclosure | Mental health chatbots must disclose AI nature. Met via the persistent AI banner. |
| CA | SB 1120 + AB 1008 + AI-related provisions | Jan 1, 2026 | Standard with AI disclosure | Requires AI disclosures, crisis detection for under-18s, AI cannot impersonate a healthcare professional. Met via AI banner, crisis overlay, 18+ age gate. |
| TN | SB 1971 | Jul 1, 2026 | Standard with AI disclosure | Prohibits AI chatbots from representing as licensed professionals. Met via product framing as educational tool, not a licensed clinician. |
| TX | HB 149 — Responsible AI Governance Act | Jan 1, 2026 | Standard | Adopts NIST AI RMF as safe harbor. WondrLink's hallucination mitigation pipeline + this compliance framework are intended to align with NIST AI RMF. |

## Comprehensive Privacy Laws (in force)

19 states have comprehensive consumer privacy laws as of mid-2026. WondrLink's posture is to apply the most protective standard globally to simplify operations:

| State | Law | Notes |
|---|---|---|
| CA | CCPA / CPRA | Sensitive personal information rules apply; GPC honored; rights surface via /api/delete_account and /api/privacy_appeal. |
| VA | VCDPA | DPIA required for sensitive data — documented in `dpia.md`. |
| CO | CPA | DPIA required; GPC honored. |
| CT | CTDPA | DPIA required; GPC honored. |
| UT | UCPA | Standard. |
| IA | ICDPA | Standard. |
| IN | ICDPA | Standard. |
| TN | TIPA | Standard. |
| TX | TDPSA | Standard. |
| OR | OCPA | GPC honored. |
| MT | MCDPA | Standard. |
| DE | DPDPA | Standard. |
| NH | (numbered statute) | Standard. |
| NJ | NJDPA | Standard. |
| KY | (statute) | Standard. |
| RI | (statute) | Standard. |
| MN | MCDPA | Standard. |
| MD | MODPA | Specific sensitive data rules for health-adjacent data. |
| NE | (statute) | Standard. |

## Pending / Active Mental Health AI Bills to Monitor

| State | Bill | Status | Watch reason |
|---|---|---|---|
| FL | Multiple bills introduced 2025–2026 | Monitor | Tracks similar framing to IL/NV. |
| MA | Pending | Monitor | Active legislative interest. |
| NH | Pending | Monitor | Active. |
| NY | Pending | Monitor | Active. |
| OH | Pending | Monitor | Active. |
| PA | Pending (post Character.AI enforcement action May 2026) | Monitor | The PA AG's action against Character.AI sets an enforcement precedent for AI-as-medicine-practitioner; relevant to all AI health products. |
| NJ | Pending | Monitor | Active. |
| NC | Pending | Monitor | Active. |
| TX | (additional bills beyond HB 149) | Monitor | Active legislative interest. |

## Review Triggers

Update this document when any of the following happens:
- A new state AI / privacy / mental health bill is enacted that may affect a covered user.
- An existing tracked bill changes status.
- The product gains or loses a feature that is sensitive to a tracked law (e.g., adding voice-based mental health features).
- A user reports an issue tied to state law.
- Quarterly review cadence (Q1 / Q2 / Q3 / Q4).

## Action Items

- [ ] Attorney to confirm exhaustiveness of the comprehensive privacy law list and any state-specific notification requirements for breach response.
- [ ] Add Q3 2026 review entry on calendar.
