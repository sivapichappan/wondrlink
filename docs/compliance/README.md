# WondrLink Compliance Documentation

> All documents in this folder are **DRAFT — INTERNAL USE — ATTORNEY REVIEW REQUIRED.**
> They were prepared during the May 2026 compliance hardening sprint. They reflect the engineering team's best effort at meeting the requirements identified in the pre-launch compliance assessment. Final wording and final positions are set by the WondrLink Foundation's healthcare-privacy attorney before public launch.

## Index

| Document | Purpose |
|---|---|
| [incident_response_plan.md](incident_response_plan.md) | Detection, containment, investigation, and FTC HBNR notification process. 60-day clock. Severity matrix, escalation chain, phase-by-phase actions. Includes the 45-day Privacy Appeal SLA workflow. |
| [subprocessor_chain.md](subprocessor_chain.md) | Every third-party vendor that processes WondrLink data — what data, what DPA/BAA status, what retention. Living document. |
| [dpia.md](dpia.md) | Data Protection Impact Assessment per GDPR Article 35 / CO / VA / CT privacy laws. Risk register and mitigations. |
| [hbnr_breach_notification_template.md](hbnr_breach_notification_template.md) | Pre-drafted breach notification templates for consumers, FTC submission, media, and state AGs. Accelerates response inside the 60-day clock. |
| [fda_non_device_memo.md](fda_non_device_memo.md) | Internal position memo on why WondrLink is not an FDA-regulated medical device under the 21st Century Cures Act CDS exemption. |
| [state_law_tracker.md](state_law_tracker.md) | Living tracker of state AI / privacy / mental health laws and WondrLink's posture toward each. Quarterly review cadence. |

## Companion Code & Migration Files

The compliance hardening sprint also produced these artifacts in other parts of the repo:

- [lib/compliance.py](../../lib/compliance.py) — constants (CURRENT_CONSENT_VERSION, BLOCKED_STATES, US_STATES) and validators (consent, age, state, metadata builder).
- [supabase_migrations/2026_05_11_compliance_v2.sql](../../supabase_migrations/2026_05_11_compliance_v2.sql) — adds `consent_metadata` JSONB and `consent_version` TEXT columns to `user_acknowledgements`. **Must be applied to production Supabase before deploy.**
- [public/index.html](../../public/index.html) — Consumer Health Data Privacy Notice modal, extended acknowledgement modal, state-restricted modal, persistent AI disclosure banner, privacy appeal form.
- [api/index.py](../../api/index.py) — extended /api/save_acknowledgement, /api/check_acknowledgement, new /api/privacy_appeal, GPC `before_request` hook.
- [lib/supabase_storage.py](../../lib/supabase_storage.py) — extended check/save acknowledgement, deletion audit log.

## Production Deployment Checklist (Compliance v2)

Before merging to main and deploying:

1. **Apply the Supabase migration** in `supabase_migrations/2026_05_11_compliance_v2.sql`. Without it, save_acknowledgement falls back to a legacy path; check_acknowledgement may not detect re-consent need.
2. **Sign DPAs/BAAs** with Supabase (HIPAA tier), Together AI, Groq, Vercel.
3. **Set env vars** (optional kill switches): `FEATURE_STRICT_COMPLIANCE=true` is the default; flip to `false` only to debug a regression. All other `FEATURE_*` flags from the prior sprint remain effective.
4. **Attorney review** of:
   - Consumer Health Data Privacy Notice (`public/index.html#consumerHealthOverlay`)
   - Privacy Policy (existing modal, now extended)
   - Terms of Use (existing modal, now extended)
   - The six DRAFT documents in this folder
5. **Procure cyber liability + tech E&O insurance.**
6. **Schedule the annual tabletop exercise** of the Incident Response Plan.
7. **Tag the deployment** as `compliance-v2-2026-05` for audit history.

## Question / Comment Routing

- Engineering: open an issue in the repo.
- Legal / regulatory: privacy@wondrlinkfoundation.org
- Incident reports: security@wondrlinkfoundation.org
- Privacy rights requests / appeals: appeals@wondrlinkfoundation.org
