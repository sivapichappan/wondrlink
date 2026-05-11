# WondrLink — HBNR Breach Notification Templates

> **DRAFT — INTERNAL USE — ATTORNEY REVIEW REQUIRED.**
> When (not if) a breach occurs, these pre-drafted templates accelerate response inside the FTC HBNR 60-calendar-day window. Final wording at the time of an incident is set by the Privacy Officer with attorney sign-off.

## A. Consumer Notification Email

**Subject:** Important Notice About Your WondrLink Account

Dear [first name or "WondrLink user"],

We are writing to let you know about a recent incident that may have affected information you provided to WondrLink. We are committed to being transparent with you and giving you the information you need to take any steps you may want to take.

**What happened.**
On [date of discovery], we [discovered / were notified] that [brief, factual description of the incident — e.g., "an unauthorized party accessed a portion of our application database" or "a misconfiguration in our authentication system allowed [scope]"]. We immediately [containment action — e.g., closed the access path, rotated credentials, engaged a forensics team].

**What information was involved.**
The information that may have been involved includes: [precise list — e.g., "email addresses, cancer diagnosis and treatment information you entered into your profile, chat conversation history"]. [If applicable: "Your password was not exposed — passwords are stored using one-way cryptographic hashing."]

**What we are doing.**
[List of remedial actions, e.g.:]
- We have closed the security gap that led to this incident.
- We have rotated all relevant credentials.
- We have engaged [outside forensics firm / law enforcement / a privacy attorney].
- We are reviewing our security practices to prevent recurrence.

**What you can do.**
- Review your WondrLink profile at https://wondrchat.vercel.app and update or delete any information you wish.
- Use the "Delete Account" option in your profile settings if you'd like us to remove all of your data.
- For health information that may have been exposed, consider discussing with your care team whether any action is appropriate on your end.

**For more information.**
If you have questions, please email us at security@wondrlinkfoundation.org. You may also contact the U.S. Federal Trade Commission at https://reportfraud.ftc.gov or 1-877-FTC-HELP.

We are deeply sorry for any concern this causes. Your trust matters to us, and we are committed to doing better.

Sincerely,
The WondrLink Team

---

## B. FTC HBNR Notification — Form Submission Fields

Submit via the FTC's Health Breach Notification online form at https://www.ftc.gov/business-guidance/privacy-security/health-breach-notification-rule

Fields to populate:

- **Reporting entity:** WondrLink Foundation
- **Reporting entity type:** Vendor of personal health records (PHR) — non-HIPAA covered.
- **Date of discovery:** [YYYY-MM-DD]
- **Date of breach (or date range if unknown):** [YYYY-MM-DD or range]
- **Number of individuals affected:** [number] — note whether US only or international scope.
- **Type of information involved:** [categories from the consumer notification, mapped to FTC field options]
- **Source of breach:** [external hacker / insider / vendor / misconfiguration / other]
- **Was information acquired by an unauthorized person:** [Yes / Suspected / No]
- **Description of incident:** [2–3 paragraph factual summary]
- **Safeguards in place before the breach:** [TLS, encryption at rest, MFA on admin accounts, RLS policies, rate limits, audit logs, de-identification before LLM transmission]
- **Steps taken in response:** [from the consumer notification, plus any law enforcement engagement]
- **Steps taken to prevent recurrence:** [post-incident remediation list]
- **Were affected individuals notified:** Yes — see consumer notification template; method and date.
- **Were the media notified:** [Yes / No — required if ≥500 residents of a single state/jurisdiction.]
- **Contact for follow-up:** Privacy Officer, privacy@wondrlinkfoundation.org

## C. Media Notification — Required if ≥500 in a single state/jurisdiction

Submit to a prominent media outlet serving the affected jurisdiction within 60 days of discovery.

**Subject:** WondrLink Foundation Notice of Incident

WondrLink Foundation is providing public notice of an incident that may have affected the information of users of its WondrLink digital health-information service residing in [state/jurisdiction]. The incident was discovered on [date] and involved [brief factual description].

WondrLink has notified all affected individuals directly. Affected users may contact security@wondrlinkfoundation.org for questions. The incident has been reported to the U.S. Federal Trade Commission as required by the Health Breach Notification Rule.

For more information, contact press@wondrlinkfoundation.org.

## D. State Attorney General Notifications

Several states require separate notification of the state AG when their residents are affected. Common thresholds and contacts (subject to current attorney verification):

| State | Threshold | Notification contact |
|---|---|---|
| California | Any resident affected | Office of the Attorney General — Privacy Enforcement |
| New York | Any resident affected | Office of the Attorney General — Privacy Bureau |
| Washington | Any resident affected (MHMDA + breach laws) | WA AG Office |
| Texas | Combined with consumer notification on a tight clock | TX AG Office |

(Verify state-by-state with attorney at incident time. The list above is a non-exhaustive starter.)

## E. Internal Communication Template (for the IC to use during response)

**To:** incident@wondrlinkfoundation.org
**Subject:** Incident [ID] — [severity] — Status Update [N]

**Status:** [Containment / Investigation / Notification / Remediation]
**Severity:** [Critical / High / Medium / Low]
**Discovery date:** [YYYY-MM-DD HH:MM UTC]
**Initial response time:** [Within target / Late by X]

**What we know:**
- [bulleted facts]

**What we don't know:**
- [open questions]

**Actions taken since last update:**
- [list]

**Next checkpoint:** [time + responsible party]
