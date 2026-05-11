# WondrLink — Incident Response Plan

> **DRAFT — INTERNAL USE — ATTORNEY REVIEW REQUIRED.**
> Prepared May 2026 as part of the compliance hardening sprint. Reviewed and finalized before public launch by a healthcare-privacy attorney.

## Purpose

Document the process WondrLink uses to detect, contain, investigate, and notify in the event of a security incident affecting personal health record (PHR) information. Designed to meet the FTC Health Breach Notification Rule (HBNR, 16 CFR Part 318) 60-calendar-day notification requirement.

## Scope

Covers any incident affecting the confidentiality, integrity, or availability of:
- User account information (email, hashed credentials, age confirmation, state of residence)
- Patient profile data (diagnosis, treatments, biomarkers, comorbidities)
- Mental health screening scores (PHQ-9, GAD-7, PSS-10, ISI, PREMM5)
- Chat conversation history
- Symptom reports
- Any consumer health data as defined by WA MHMDA

## Definitions

- **Incident** — any event that may compromise the confidentiality, integrity, or availability of WondrLink data.
- **Breach** — an incident confirmed to involve unauthorized acquisition of unsecured PHR information.
- **Discovery** — the date the incident is first known or reasonably should have been known.

## Detection Sources

- Supabase audit logs (database access anomalies, RLS policy violations)
- Vercel function logs (suspicious request patterns, rate-limit spikes)
- Together AI / Groq API alerts (account compromise notifications)
- User reports submitted to security@wondrlinkfoundation.org
- Internal monitoring (rate-limit and authentication failure dashboards)

## Severity Classification

| Severity | Criteria | Initial response time |
|---|---|---|
| Critical | Active exfiltration; >100 user records confirmed exposed | < 1 hour |
| High | Confirmed unauthorized access; <100 records affected | < 4 hours |
| Medium | Suspicious access pattern; no confirmation of exposure | < 24 hours |
| Low | Minor policy violation, no data risk | < 72 hours |

## Internal Escalation Chain

Within the initial response time:
1. **Incident Commander (IC)** — engineering lead. Owns triage, scope, communication.
2. **Privacy Officer** — Foundation leadership designee. Owns notification decisions, regulatory contacts.
3. **External counsel** — healthcare-privacy attorney on retainer.
4. **Engineering on-call** — implements containment.

All four are looped in via a single email distribution: `incident@wondrlinkfoundation.org`.

## Response Phases

### Phase 1 — Containment (hours 0–4)
- Disable affected credentials, rotate API keys.
- Suspend suspicious accounts.
- Preserve logs (immutable copy to a separate Supabase project for forensics).
- IC briefs Privacy Officer within 2 hours.

### Phase 2 — Investigation (hours 4–72)
- Determine scope: which records, which users, what time window.
- Determine cause: external breach, insider, misconfiguration, vendor compromise.
- Document timeline of events with timestamps and evidence.
- Privacy Officer briefs external counsel.

### Phase 3 — Notification Decision (day 3–7)
- Counsel + Privacy Officer determine whether the incident constitutes a breach under HBNR.
- If yes: notification clock starts at Discovery date (not Decision date).
- Decision documented in writing.

### Phase 4 — Notifications (within 60 calendar days of Discovery)

**Consumer notification** — required for every breach affecting unsecured PHR data:
- Sent via email to each affected user (template: `hbnr_breach_notification_template.md`).
- Plain language description of what happened, what data, what we are doing, what users can do.

**FTC notification** — required:
- Submit via the FTC's Health Breach Notification online form within 60 days.
- If ≥500 individuals affected: notification within 60 days, not extended.
- If <500 individuals: may be batched annually but no later than 60 days after end of calendar year.

**Media notification** — required if ≥500 residents of a single state or jurisdiction are affected:
- Prominent media outlet serving that jurisdiction.
- Within 60 calendar days.

**State Attorney General notification** — separately required by several state laws (CA, NY, WA, others). Counsel determines per state.

### Phase 5 — Remediation (ongoing)
- Implement fixes to prevent recurrence.
- Update relevant detection rules.
- Postmortem document filed in `docs/compliance/postmortems/YYYY-MM-incident.md`.

## Privacy Appeal SLA Workflow

Appeals are submitted via `/api/privacy_appeal` and persisted to `patient_profiles.raw_profile.privacy_appeals[]`. The Privacy Officer reviews the queue **weekly**. The SLA is 45 calendar days from the appeal `timestamp`. One 45-day extension is permitted where reasonably necessary; user must be notified before the original SLA expires.

Resolution states:
- `submitted` — created, awaiting review
- `under_review` — Privacy Officer is investigating
- `granted` — request honored; resolution_note records what was done
- `partially_granted` — limited honor (e.g., partial deletion)
- `denied` — with reason
- `extended` — one-time SLA extension

If an appeal is denied, the response email includes the WA AG Office contact (for WA residents) and other state-AG escalation paths.

## Annual Tabletop Exercise

Once per year, the IC and Privacy Officer run a simulated incident to validate this plan. Date is tracked in `state_law_tracker.md`.

## Document Maintenance

- Reviewed quarterly during the compliance review.
- Updated whenever a new sub-processor is added, an endpoint is added, or a state law changes.
- Last reviewed: TBD (post attorney review).
