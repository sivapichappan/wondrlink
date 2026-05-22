# Incident Response Plan — Tabletop Scenarios

**Status:** DRAFT — ready to run once IC / Privacy Officer / counsel are seated.
**Companion:** [docs/compliance/incident_response_plan.md](incident_response_plan.md)
**Cadence:** Annually + after any significant architecture change.
**Owner:** Incident Commander (TBD)

A plan that's never exercised is a plan that breaks under load. These three drillable scenarios let the team rehearse the IRP before launch. Each is timed and includes the decision points that map back to the actual plan sections.

> ⚠️ **DRAFT — ATTORNEY REVIEW REQUIRED.** Counsel should review the notification decision trees and ratify the 60-day clock-start interpretation in scenario 1 in particular.

How to run a tabletop:
1. Block 90 minutes on the calendar with IC, Privacy Officer, external counsel (or proxy), on-call engineering lead.
2. Read the scenario aloud at T=0.
3. The facilitator advances the clock in 30-minute increments and reads the injects.
4. The team makes decisions in real time + writes them on a shared board.
5. At the end, compare the team's decisions against the "Reference decisions" section. Capture gaps as follow-ups.

---

## Scenario 1 — "Together AI Log Leak (de-identified)"

### Setup

It's a Tuesday morning. Together AI's security team emails our `privacy@wondrlinkfoundation.org` alias at 09:14 ET:

> We're notifying you of a logging configuration regression in our inference API that retained customer-submitted prompt+completion pairs beyond the documented 30-day window. The retention window expanded to ~120 days for a subset of customers between 2026-04-12 and 2026-05-18. The retained logs were stored in our standard production S3 bucket with the standard access controls — no third party accessed the bucket. We have purged the affected logs as of 18:00 UTC yesterday.
>
> Our internal audit identified 547 of your customer accounts (based on tenant ID) as affected. Approximate prompt count: 8,400.
>
> We do not believe any third party accessed the logs. We are not classifying this as a security breach but we are notifying you so you can comply with your downstream obligations.

### Injects

- **T=0** (09:14): the email above arrives. Auto-forwarded to the IC and Privacy Officer.
- **T=30**: an engineer notes that all our queries to Together AI are de-identified — names, ZIPs, DOBs, addresses, phones, emails, SSNs, MRNs, insurance IDs, account numbers were stripped before send. (See `lib/deidentify.py`.)
- **T=60**: counsel asks: "do we still have HBNR notification obligations if the leaked content was de-identified per HIPAA Safe Harbor methodology?" The team has 30 minutes to answer.
- **T=120**: a journalist on Twitter posts a screenshot of the Together AI advisory and tags us. (Inject 3: external pressure.)
- **T=180**: counsel returns with: "the 2024 HBNR amendments treat 'PHR identifiable health information' broadly; even de-identified queries that contain treatment names, biomarkers, and stage information may be considered identifiable when correlated with the user account ID that Together AI received. We need to decide now whether to notify."
- **T=300 (5 hours in)**: a second journalist posts. Press inquiries start.
- **T=24h**: forensic confirmation that no third party accessed the bucket.

### Reference decisions

1. **Severity classification:** Medium → escalate to High if counsel concludes HBNR notification is required.
2. **HBNR clock start:** The HBNR 60-day clock starts at *discovery* of the breach, which is when we received the Together AI email. T=0 = 09:14 today. Decision deadline for notification: 60 days from today.
3. **Notification decision:** Likely YES based on the 2024 HBNR broad-PHR-information definition. Counsel-led; engineering doesn't unilaterally decide.
4. **Consumer notification:** prepare from [docs/compliance/hbnr_breach_notification_template.md](hbnr_breach_notification_template.md). Send via the user's account email; in-product banner on next login.
5. **FTC notification:** required if HBNR applies. File via the FTC's online form within 60 days of discovery.
6. **Media notification:** required if ≥500 individuals are affected — at 547 accounts we cross the threshold. Issue a press release; counsel reviews.
7. **State AG notifications:** state-by-state thresholds vary; counsel maps which states require notification (CA + several others have lower thresholds).
8. **Remediation:** evaluate whether the de-identification pipeline can be tightened further. The 547-account number tells us we sent thousands of queries during the window; that's working as designed (we route all chat through Together AI). What we should review: did the runtime PII guard (Task 10) catch anything? Did any non-de-identified payload land in the logs by accident?
9. **Post-mortem:** open within 14 days of the notification deadline; counsel-led; lessons-learned captured in this doc as a decision log entry.

### Practice questions

- Can the team find the named IC + Privacy Officer + counsel within the first 30 minutes?
- Does the team correctly identify the 60-day clock-start moment?
- Does the team avoid the trap of treating "de-identified = no notification"?
- Does the team escalate the press response separately from the notification response?

---

## Scenario 2 — "Identifiable Data Leak (caught in dev)"

### Setup

It's a Friday afternoon. The de-identification regression test (`tests/test_deidentify.py`) suddenly starts failing on `main`:

```
FAILED tests/test_deidentify.py::test_deidentify_raw_profile_strips_identifiers
  - 'jane doe' is contained here:
    {'patient': {'name': 'jane doe', 'address': '...', ...}}
```

A PR that landed two days ago refactored the profile schema and renamed the `patient` key to `subject` in the JSON shape — but only updated the read path, not the de-identification pipeline. For two days, the deidentification function has been silently no-op-ing on the new profile shape, while everything else worked.

### Injects

- **T=0**: a developer runs the test suite and notices the failure. Pings the on-call engineering lead in Slack.
- **T=15**: confirmed — affected window is 2026-05-19 09:00 → 2026-05-21 14:00 (about 53 hours).
- **T=30**: engineering checks the chat logs for the affected window. Approximate impacted user count: 23. Approximate query volume: 184.
- **T=60**: a query of the runtime PII guard logs (`grep PII-LEAK-BLOCKED`) shows zero hits during the window. The guard did NOT catch this because field-level identifiers in dicts (like `name: "jane doe"`) aren't matched by the regex patterns — those patterns target free-text PII (SSN, phone, email), not structural dict fields.
- **T=90**: forensic question — did the LLM ever see the identifiable data? Yes. The system prompt includes the profile dict serialized as JSON; identifiable fields were included in the JSON for ~184 queries.
- **T=120**: counsel asks: "is this a 'breach of security' under the HBNR definition, or an internal data-handling regression that we caught before any third party accessed it?"

### Reference decisions

1. **Severity classification:** Critical — identifiable data left our perimeter, even though we caught it in dev. The clock starts at T=0 (when the test failure was first observed).
2. **Containment (0–4h):** revert the offending PR or hot-patch the de-identification pipeline to handle the renamed `subject` key. The PII guard should also be widened to scan dict keys + values, not just free text — file a follow-up.
3. **Notification decision:** YES. The 184 queries during the window were sent to Together AI with identifiable fields. The 23 affected users were exposed to a sub-processor (Together AI) without our intended de-identification step.
4. **HBNR clock start:** T=0 (the moment of discovery).
5. **Together AI obligation:** notify our Together AI account contact + invoke any DPA deletion-on-request clause for the affected logs (deletion within their retention window).
6. **Consumer notification:** specific to the 23 affected users. In-product banner + account email. Less alarming framing than scenario 1 since we caught it ourselves before any third party accessed the data.
7. **FTC notification:** YES per HBNR amendments — exposure to a sub-processor without the intended controls satisfies the trigger.
8. **Media notification:** NOT required (under 500 individuals).
9. **Remediation:**
   - Widen `detect_pii_leaks()` to walk dict keys + values for known PII field names (`name`, `dob`, `phone`, `email`, `ssn`, `mrn`, `insuranceId`, `accountNumber`).
   - Make the de-identification function fail-closed on unknown profile-key shapes: if it doesn't recognize the top-level key, raise instead of silently no-op-ing.
   - Add a CI guard that diffs the de-identification spec against the current profile schema on every PR that touches `lib/profile_utils.py` or `lib/deidentify.py`.

### Practice questions

- Does the team correctly identify the PII guard miss as a separate finding?
- Does the team avoid the trap of "we caught it ourselves so we don't need to notify"? (HBNR doesn't care who caught it; the trigger is the exposure.)
- Does the team write the corrective actions before the post-mortem?

---

## Scenario 3 — "Account Credential Theft"

### Setup

It's a Monday evening. A user emails `info@wondrlinkfoundation.org`:

> Hi, someone has been using my WondrChat account. I see chat history I didn't write — questions about a cancer I don't have. I changed my password last week but it's still happening. What do I do?

### Injects

- **T=0**: the email arrives. Triaged to support, then escalated to engineering when the "someone is using my account" detail registers.
- **T=30**: support confirms: chat-history rows in Supabase for this user contain queries the user denies writing. Most recent: T-2h.
- **T=60**: engineering checks Supabase auth logs. Login from a different IP geography (different country) two weeks ago; the user's normal IP is in NY, the foreign login is from Eastern Europe.
- **T=90**: engineering invalidates all active sessions for the account. Forces password reset. Notifies the user via the on-file email.
- **T=120**: the user's reply confirms the lockout is now in effect.
- **T=180**: counsel asks: "is this a breach under HBNR? Under MHMDA? Do we owe notification?"

### Reference decisions

1. **Severity classification:** High (individual account compromise, not a system-wide event).
2. **Containment (0–4h):** invalidate sessions, force password reset, lockout the account temporarily — done.
3. **Investigation (4–72h):**
   - Did the unauthorized party download / export data? Check the chat-history export endpoint logs.
   - Did the unauthorized party post messages elsewhere with our content?
   - Is this part of a credential-stuffing campaign affecting other accounts? Run a sweep of recent logins from the same IP range.
4. **HBNR analysis:** an individual account credential compromise where the credentials were not stolen *from us* (i.e. the user reused a password from a leak elsewhere) is generally NOT an HBNR-covered "breach of security" of WondrChat. Counsel-led; we don't unilaterally decide.
5. **MHMDA analysis:** same framework. The user's data may have been viewed by an unauthorized party, but the unauthorized access didn't go through our security perimeter — it went through a credential the user reused.
6. **Notification to the affected user:** YES. Explain what we saw, what we did, recommend they update any other accounts that used the same password.
7. **Notification to anyone else:** Probably NO. If the credential-stuffing sweep reveals a wider campaign, we re-evaluate.
8. **Remediation:**
   - Consider implementing breached-password screening at signup + login (Have I Been Pwned API).
   - Consider rate-limiting login attempts from new IP geographies as a sentinel for credential stuffing.
   - Add a self-service "see your active sessions" affordance so users can detect this earlier.

### Practice questions

- Does the team distinguish between "user's credentials were stolen from us" (an HBNR-covered breach) and "user's credentials were stolen from somewhere else and reused on us" (generally not HBNR-covered)?
- Does the team take containment actions before deciding on notifications?
- Does the team treat the user's email as a fact-finding lead rather than a complaint-handling task?

---

## After every tabletop

1. Open a decision log entry in this file: date, scenario, team members present, decisions reached, follow-ups assigned.
2. Update the Incident Response Plan with any gaps discovered.
3. Add or update fixtures in `tests/test_deidentify.py` if a scenario revealed a regression vector the tests don't cover.
4. Update [docs/compliance/state_ai_law_tracker.md](state_ai_law_tracker.md) if a scenario surfaced a state-specific obligation not yet tracked.

---

## Decision log

- **2026-05-20** — scenarios authored; ready to run once named IC + Privacy Officer + counsel are seated. No tabletop has been run yet.
- _(future entries…)_

---

*Companion docs:* [Incident Response Plan](incident_response_plan.md) · [HBNR Breach Notification Template](hbnr_breach_notification_template.md) · [DPIA](dpia.md) · [Sub-processor Chain](subprocessor_chain.md) · [NIST AI RMF Mapping](nist_ai_rmf_mapping.md)
