# WondrLink — Sub-Processor Chain

> **DRAFT — INTERNAL USE — ATTORNEY REVIEW REQUIRED.**
> Living document. Update whenever a vendor is added, removed, or contract terms change. Last reviewed: May 2026.

## Purpose

Document every third-party service that processes WondrLink user data on our behalf, with: scope of data shared, contractual posture, retention terms, deletion guarantees, and contact path. Required for:
- WA MHMDA § 4 (sub-processor disclosure in the Consumer Health Data Privacy Notice)
- GDPR Article 28 (processor agreements with each sub-processor)
- State comprehensive privacy laws (CA, CO, CT, VA — processor terms required)

## Summary Table

| Sub-Processor | Function | Data Shared | DPA/BAA | Retention | Contact |
|---|---|---|---|---|---|
| Supabase | Postgres database + auth | All stored data | DPA: TBD (sign before launch); HIPAA tier available | While account active; backups auto-purged per Supabase PITR retention | privacy@supabase.io |
| Together AI | Primary LLM inference | De-identified query text + retrieved guideline excerpts | DPA: TBD (sign before launch) | Per Together AI ToS (~30 days typical) | privacy@together.ai |
| Groq | Fallback LLM + verification | De-identified query text + retrieved guideline excerpts | DPA: TBD (sign before launch) | Per Groq ToS | privacy@groq.com |
| Vercel | Web hosting + serverless functions | Request metadata (no application data persists at Vercel) | DPA: available via Vercel Pro plan | Function logs: short retention per Vercel ToS | privacy@vercel.com |
| ClinicalTrials.gov (US NIH) | Clinical trial search | Search terms only (no user identifiers) | Not applicable (public records API) | N/A | clinicaltrials@nih.gov |

## Per-Vendor Details

### Supabase, Inc.

- **Function:** Database (PostgreSQL with pgvector), authentication, file storage.
- **Data scope:** All persisted application data — auth records, profiles, chat messages, screening scores, acknowledgements, appeals, vector embeddings.
- **Encryption:** TLS in transit; AES-256 at rest.
- **Contractual posture:** Supabase offers a HIPAA-compliant tier with a Business Associate Agreement. **Action: confirm WondrLink's plan; sign DPA before public launch.**
- **Retention:** Application data is held while user account exists. On account deletion, application rows are purged immediately. Supabase database backups (Point-in-Time Recovery) are retained for the platform-default window (7 days on the Free/Pro tier; configurable on Team/Enterprise). Backups are encrypted and automatically purged at the end of the window.
- **Deletion API:** Soft-delete via row-level removal is honored immediately; backup rotation is automatic.
- **Sub-processor of Supabase:** AWS (storage infrastructure).
- **Audit:** Supabase publishes SOC 2 Type II; available on request.

### Together AI

- **Function:** Primary LLM inference (Llama 3.3 70B).
- **Data scope:** WondrLink sends each user query through a de-identification pass (`sanitize_query`) before transmitting to Together. Together receives a de-identified question plus retrieved CRC guideline excerpts. Together does not receive direct identifiers (no names, no DOB, no MRN, no email, no IP).
- **Contractual posture:** Standard API customer. **Action: review Together's enterprise DPA terms; sign before public launch.**
- **Retention:** Per Together AI's published Terms of Service. Inference logs are typically retained for ~30 days for abuse monitoring. Together has stated that API data is not used for model training (verify in latest ToS).
- **Deletion API:** Together does not currently expose a per-user deletion endpoint at the standard API tier. Mitigation: WondrLink only sends de-identified content, so log retention does not contain identifiable user data.
- **Audit:** SOC 2 Type II available.

### Groq, Inc.

- **Function:** Fallback LLM inference (Llama 3.1 8B) for primary chat when Together is unavailable; also runs the second-pass verification model in the hallucination mitigation pipeline.
- **Data scope:** Same as Together — de-identified query + guideline excerpts.
- **Contractual posture:** Standard API customer. **Action: review Groq's DPA terms; sign before public launch.**
- **Retention:** Per Groq ToS.
- **Audit:** Pending; verify SOC 2 status.

### Vercel, Inc.

- **Function:** Web application hosting, serverless function execution.
- **Data scope:** WondrLink stores no application data on Vercel. Vercel sees HTTP request metadata (path, headers, IP), serverless function logs (which we keep minimal), and static assets.
- **Contractual posture:** Vercel Pro plan includes a DPA. **Action: ensure DPA is signed.**
- **Retention:** Function logs retained for a short window per the active plan; not configurable below Enterprise.
- **Audit:** SOC 2 Type II published.

### ClinicalTrials.gov (US NIH)

- **Function:** Public registry of clinical trials. WondrLink queries the v2 API to find trials matching a user's profile.
- **Data scope:** Only search terms (cancer type, biomarker, ZIP for radius, age) are sent. No WondrLink identifiers, no user-level data.
- **Contractual posture:** Public records API. No DPA required.
- **Retention:** N/A — we send queries, not data; NIH retains general API traffic logs per federal records policy.

## Onboarding a New Sub-Processor

Before adding a new vendor:
1. Document above with all fields.
2. Sign a DPA (or BAA if HIPAA scope attaches).
3. Update the Consumer Health Data Privacy Notice (`public/index.html#consumerHealthOverlay`).
4. Update the Privacy Policy if material.
5. Re-acknowledgement is **not** required for routine sub-processor changes — but **is** required if the new processor expands the data scope materially (in which case `CURRENT_CONSENT_VERSION` is bumped in `lib/compliance.py`).

## Removing a Sub-Processor

1. Issue deletion request to the vendor (per their DPA).
2. Remove from the table above.
3. Confirm in next quarterly compliance review.

## Open Items

- [ ] Sign Supabase BAA / HIPAA-tier DPA.
- [ ] Confirm Together AI DPA terms; sign.
- [ ] Confirm Groq DPA terms; sign.
- [ ] Confirm Vercel DPA is signed under current plan.
