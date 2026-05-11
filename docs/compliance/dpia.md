# WondrLink — Data Protection Impact Assessment (DPIA)

> **DRAFT — INTERNAL USE — ATTORNEY REVIEW REQUIRED.**
> Prepared May 2026. Applicable to GDPR Article 35, Colorado / Virginia / Connecticut / Texas privacy law risk assessment requirements, and WA MHMDA risk evaluation.

## 1. Identity of the Data Controller / Processor

- **Controller:** WondrLink Foundation
- **Processing role:** Direct-to-consumer health-information service
- **Contact:** privacy@wondrlinkfoundation.org

## 2. Description of the Processing

### Nature of processing
WondrLink processes user-submitted information (medical profile, questions, self-administered screening responses) and combines it with retrieved educational content from a curated corpus of cancer guidelines to produce conversational answers. Processing involves de-identification, retrieval-augmented generation via third-party LLMs, and persistence of session history.

### Categories of data
- **Special category (sensitive):** health data — cancer diagnosis, treatments, biomarkers, comorbidities, symptoms, mental health screening scores.
- **Personal:** email, age confirmation, state of residence, ZIP code.
- **Inferred:** treatment line, biomarker implications, urgency level, retrieval confidence — all derived during processing and persisted only as session metadata.

### Categories of data subjects
Adults (18+) affected by colon cancer (patients, caregivers, family members) in the United States. Excluded by state policy: residents of Illinois and Nevada.

### Purposes
- Provide personalized cancer education.
- Match users against publicly listed clinical trials.
- Track self-administered screening trends for user awareness.
- Improve service through de-identified aggregate analysis.

### Recipients
Sub-processors only (see `subprocessor_chain.md`). No data is shared with insurers, employers, advertisers, or data brokers.

## 3. Necessity and Proportionality

### Legal basis (GDPR)
- Article 6(1)(b) — performance of a contract (terms of use)
- Article 9(2)(a) — explicit consent for processing health data
- Each consent is collected independently per MHMDA at the acknowledgement gate.

### Necessity
The service cannot function without the user-submitted health profile (which drives personalization) and chat history (which provides continuity). Both are minimum-necessary for the purpose.

### Proportionality
- We de-identify before transmitting to sub-processors.
- We do not collect biometric data, location at higher precision than ZIP, or financial data.
- Retention is limited to the active account; deletion is honored immediately.

## 4. Risk Assessment

| Risk | Likelihood | Severity | Mitigations |
|---|---|---|---|
| Re-identification of de-identified data | Low | High | Aggressive de-identification (`sanitize_query`); reviewed quarterly. Sub-processors contractually bound to not attempt re-identification. |
| Sub-processor data breach | Low–Medium | High | Only de-identified queries sent. SOC 2 audit of each vendor required. DPAs include breach notification clauses. |
| Insider misuse | Low | High | RLS policies on Supabase tables; admin client used only for explicit operations; audit logs retained. |
| Hallucinated medical content | Medium | Medium | Engineered mitigation pipeline (off-topic detection, second-pass LLM verification, source-grounded prompts, inline citations). |
| User mis-disclosure (e.g. entering another person's data) | Low | Medium | Terms of Use require accurate self-data; product UI does not facilitate third-party data entry. |
| State law enforcement (IL/NV residents accessing) | Low | Medium | Geographic restriction enforced at signup and at acknowledgement; soft-deactivation flow on existing accounts. |
| Loss of consent record | Low | High | `user_acknowledgements.consent_metadata` JSONB persisted with audit fields including IP hash and timestamp. |

## 5. Compliance & Proportionality Checks

- **Lawfulness:** explicit consent + contract; documented at acknowledgement.
- **Fairness:** rights and processing described in plain language in Consumer Health Data Privacy Notice and Privacy Policy.
- **Transparency:** policies linked at signup, in acknowledgement, in chat footer; AI nature disclosed in persistent banner.
- **Purpose limitation:** processing strictly limited to documented purposes.
- **Data minimization:** profile fields are optional except age and state; chat history is configurable to delete.
- **Accuracy:** users can edit profile at any time.
- **Storage limitation:** retained while account active; deletion within 30 days of request.
- **Integrity and confidentiality:** TLS in transit, AES-256 at rest, RLS on tables, rate limiting.
- **Accountability:** this DPIA, incident response plan, sub-processor chain, and quarterly review cadence.

## 6. Decision

This processing is judged as **low-to-medium residual risk** after mitigations. The single highest residual risk is sub-processor data handling — addressed via DPA terms and de-identification at the boundary. No additional Article 36 consultation with a supervisory authority is judged necessary at this time. To be re-evaluated after the first quarterly compliance review post-launch.

## 7. Review Cadence

- Quarterly review during the compliance review cycle.
- Upon adding a new sub-processor.
- Upon material change in data scope.
- Upon any incident response postmortem.
