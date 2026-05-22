# WondrChat Compliance Response — Current State vs. May 8 Assessment

**Prepared:** 2026-05-20
**Source assessment:** `wondrchat-compliance-assessment (1).md` (dated 2026-05-08)
**Scope:** Inventory of what has shipped since the May 8 review + concrete gap list to reach "perfect compliance."

> ⚠️ **This is an engineering-side status document.** It is not legal advice and does not substitute for the formal attorney review the May 8 assessment recommends. Several "PRESENT" items here are explicitly marked DRAFT — ATTORNEY REVIEW REQUIRED in the source files and remain conditional on that review.

---

## Executive Snapshot

The May 8 assessment landed at a moment where most compliance work had been scoped but very little had been built. Since then, a meaningful slice of the **Tier 1 critical-path checklist** has been implemented in code, policy, and documentation. The headline picture as of 2026-05-20:

| Status | Count | Notes |
|---|---|---|
| ✅ Shipped & enforced in code | 13 of 25 audit items | MHMDA notice, three-checkbox consent, age gate, IL/NV block, de-identification, crisis short-circuit, GPC honoring, persistent AI banner, etc. |
| 🟡 Shipped in policy/docs, **pending counsel + signed vendor contracts** | 6 | Privacy Policy, Consumer Health Data Notice, Incident Response Plan, DPIA, Sub-processor chain, Terms of Use |
| 🔴 Still absent or partial | 6 | DPAs/BAAs not signed, GDPR Article 30 RoPA, EU Representative, SCCs, CSP header, automated WCAG testing, PRO-CTCAE Grade 3+ escalation |

**The single biggest remaining blocker is not engineering work — it is the formal attorney review and the signed vendor agreements (BAA / DPA / SCC) with Supabase, Together AI, Groq, and Vercel.** Most other gaps are tractable inside a 2–3 week sprint.

---

## Framework-by-Framework Response

The numbering below mirrors the May 8 assessment.

### 1. HIPAA — Likely Not a Covered Entity

**May 8 finding:** "Watch vendor chains." Acceptable architectural pattern (de-identify before LLM); no provider relationship today; vendor-chain risk if a clinic ever integrates.

**Current state:**
- ✅ De-identification module shipped at [lib/deidentify.py:30-186](lib/deidentify.py#L30) — strips name, ZIP, DOB, address, phone, email, SSN, MRN, insurance ID, account numbers; converts dates to relative timeframes; preserves age band, race/ethnicity, cancer type/stage/biomarkers/treatments.
- ✅ Called at the chat boundary before any prompt is sent to Together AI / Groq ([api/index.py:683-689](api/index.py#L683)).
- ✅ De-identification attestation surfaced in the Privacy Policy ([public/index.html:6389](public/index.html#L6389)) and the Consumer Health Data Privacy Notice ([public/index.html:6389](public/index.html#L6389)) for user transparency.
- 🟡 No signed BAA with Supabase, Together AI, or Groq. Vendor chain documented at [docs/compliance/subprocessor_chain.md](docs/compliance/subprocessor_chain.md) but signatures are **TBD** ([line 85](docs/compliance/subprocessor_chain.md#L85)).
- 🔴 No internal "we are not a Covered Entity" memo signed off by counsel yet.

**To reach perfect compliance:**
- Have counsel author + sign the not-a-Covered-Entity memo so the position is documentable in an audit.
- Get Supabase HIPAA-tier BAA signed (they offer this on the Pro plan).
- Confirm Together AI / Groq Business / Enterprise plans that include BAA support; decide whether to upgrade now (defensive) or only if a clinic partnership ever attaches.
- Add an explicit "WondrChat does not provide HIPAA-compliant services" line to marketing copy to neutralize FTC §5 deception risk (we're already careful — make it explicit).

---

### 2. FTC Health Breach Notification Rule (HBNR) — APPLIES

**May 8 finding:** No documented breach response plan. Civil penalty exposure up to ~$51,744 per violation.

**Current state:**
- ✅ Full Incident Response Plan at [docs/compliance/incident_response_plan.md](docs/compliance/incident_response_plan.md):
  - 60-day HBNR clock documented ([lines 7-8, 72](docs/compliance/incident_response_plan.md#L7))
  - Severity matrix (Critical <1h, High <4h, Medium <24h, Low <72h) ([lines 34-41](docs/compliance/incident_response_plan.md#L34))
  - Five response phases: Containment / Investigation / Notification decision / Notifications / Remediation ([lines 53-92](docs/compliance/incident_response_plan.md#L53))
  - 45-day appeal SLA + one 45-day extension ([lines 94-97](docs/compliance/incident_response_plan.md#L94))
  - Escalation chain documented (IC, Privacy Officer, external counsel, on-call eng)
- ✅ Pre-drafted notification templates at [docs/compliance/hbnr_breach_notification_template.md](docs/compliance/hbnr_breach_notification_template.md) (consumer email, FTC form, media if ≥500, state AG).

**To reach perfect compliance:**
- Tabletop-exercise the plan at least once before launch. Run a fake "Together AI logs leaked 500 patients' de-identified queries — what do we do?" drill and time the response.
- Identify the named Privacy Officer + IC + backup IC (the plan references roles; we need named people in the seat).
- Wire a privacy@wondrlinkfoundation.org alias to the actual IC's pager.
- Bind cyber liability + tech E&O insurance (Tier 2 item, but pull this forward — incident handling without insurance is materially riskier).

---

### 3. Washington My Health My Data Act (MHMDA) — MAJOR GAP IN ASSESSMENT, MOSTLY CLOSED NOW

**May 8 finding:** The single most urgent item. Treble damages up to $25,000 with private right of action. Required: separate Consumer Health Data Privacy Notice, separate opt-in for collection AND for sharing, third-party list with contact info, 45-day access/deletion SLA with appeals, no selling without separate authorization, deletion that flows through to processors.

**Current state:**
- ✅ **Separate Consumer Health Data Privacy Notice** at [public/index.html:6338-6414](public/index.html#L6338) — distinct modal/page, linked from the homepage independently of the general Privacy Policy. MHMDA rights are extended to **all users regardless of state** ([line 6351](public/index.html#L6351)) to avoid maintaining two consent flows.
- ✅ **Three independent opt-in checkboxes at signup** ([public/index.html:6312-6326](public/index.html#L6312)):
  - `ackConsentCollection` — health data collection
  - `ackConsentSharing` — de-identified sharing with LLM providers
  - `ackConsentTerms` — ToU + Privacy Policy
  - All default to unchecked. Server-side validation in [lib/compliance.py:74-103](lib/compliance.py#L74) rejects signups missing any of the three with a specific error identifying which consent failed.
- ✅ **Sub-processor list with contact info** in the Consumer Health Data Notice ([lines 6383-6385](public/index.html#L6383)) and at [docs/compliance/subprocessor_chain.md](docs/compliance/subprocessor_chain.md).
- ✅ **Account deletion endpoint** at [api/index.py:2127-2151](api/index.py#L2127) — deletes user from `patient_profiles`, `chat_history`, `acknowledgements`, `appeals`, `rate_limits`, etc., then deletes the auth user via Supabase admin client.
- ✅ **Appeal process** documented in the Incident Response Plan ([docs/compliance/incident_response_plan.md:94-97](docs/compliance/incident_response_plan.md#L94)) — 45-day SLA, one 45-day extension allowed.
- ✅ **GPC opt-out honoring** at [api/index.py:58-64](api/index.py#L58) — server-side detection of `Sec-GPC: 1` header; stored in request context.
- 🟡 Deletion does **not currently cascade to Together AI / Groq logs**. Vendor ToS governs retention (typically ~30 days, but depends on plan). This is acceptable for de-identified data; **not acceptable if any identifiable data ever escapes the de-identification layer.**

**To reach perfect compliance:**
- Sign DPAs with Supabase, Together AI, Groq, Vercel that include the MHMDA-required deletion-on-request flow-through obligation. **This is the gating item.**
- Build a "Withdraw consent" UI surface that's distinct from "Delete account." Right now they're effectively merged; MHMDA technically asks for separate affordances.
- Verify the de-identification step never sends identifiable data; add a regression test (assertion) that runs against fixtures of profile + raw prompt and confirms no identifiers leak.
- Document an explicit retention period (e.g., "We retain your data while your account is active and for 30 days after deletion to allow for restoration; backups are purged within 90 days") instead of the current "as long as account is active" language.

---

### 4. State AI Mental-Health Laws (IL, NV, UT, CA, TN, TX) — MATERIAL RISK, NOW HEAVILY MITIGATED

**May 8 finding:** Patchwork of laws. IL WOPR Act + NV AB 406 the immediate concerns. No state geo-restriction. No prominent persistent AI disclosure.

**Current state:**
- ✅ **IL and NV blocked at signup** by state ([lib/compliance.py:28-34](lib/compliance.py#L28)). Server-side validation returns 422 with a user-facing explanation ([lines 113-136](lib/compliance.py#L113)). Frontend surfaces a "service not available in your state" modal ([public/index.html:6418-6429](public/index.html#L6418)).
- ✅ **Persistent AI-disclosure banner** in the chat UI at [public/index.html:7264-7266](public/index.html#L7264) — "You're chatting with an AI assistant — not a person, not medical advice. AI can make mistakes; please verify important information with your care team."
- ✅ **Mental-health screening framing is strictly educational** ([public/index.html:6559](public/index.html#L6559)): "Mental health screening tools (PHQ-9, GAD-7, PSS-10, ISI) display raw scores with standard severity labels. These are not diagnostic tools. Share your results with your healthcare provider for proper evaluation."
- ✅ **System prompt is hardened against therapy-style language** at [lib/prompts/base.py:75-89](lib/prompts/base.py#L75) — forbids "you should / must / need to / have to / ought to / tell your doctor" and required replacements ("consider", "it might help", "let your team know"). Frame as collaborative ("we can look at", "let's explore"). Hard rule enforced with post-response filter fallback ([line 98](lib/prompts/base.py#L98)).
- ✅ **Crisis short-circuit** at [lib/confidence.py:327-506](lib/confidence.py#L327) — hardcoded 988 / 741741 / 911 responses bypass the LLM entirely for ~60 keyword patterns (self-harm, medical emergency, urgent oncology).
- 🟡 **CA under-18 specific logic absent.** Currently mitigated by the 18+ age gate, but California's chatbot law (effective 2026-01-01) requires crisis-detection guardrails specifically for under-18 users. Our defense is "we don't accept under-18 users" rather than "we handle them safely." Acceptable as long as the age gate holds.

**To reach perfect compliance:**
- Add UT and TN to the disclosure-required state list explicitly in code, even if the banner already covers them globally. Documenting per-state coverage is defensible.
- Decide on TX HB 149 posture — adopt NIST AI RMF as safe harbor and document the mapping. This is a documentation exercise, not an engineering one.
- Run a transcript red-team of 50 representative chats and have a clinical-regulatory attorney flag any response that crosses "education" into "specific recommendation." Track findings as system-prompt edits.
- Consider raising the age gate to require a date-of-birth picker (with year ≤ current year - 18) instead of a single 18+ checkbox. Self-declaration is the floor; DOB is the conservative bar.

---

### 5. State Unauthorized Practice of Medicine — RISK FROM PA CASE

**May 8 finding:** The PA action against Character.AI is highly relevant. Disclaimers alone are not a shield. Deep personalization could be read as functioning as a clinical advisor.

**Current state:**
- ✅ Persistent disclaimer banner ([public/index.html:7264](public/index.html#L7264)).
- ✅ Per-response disclaimer footer applied via system prompt ([lib/prompts/base.py](lib/prompts/base.py)) and the visible footer at [public/index.html JS rendering ~line 11001](public/index.html#L11001) — "This is an educational support tool, not medical advice."
- ✅ System prompt hard rules against first-person clinical directives.
- ✅ Surveillance schedules explicitly defer to oncology team ([lib/surveillance.py:73-77](lib/surveillance.py#L73)) — "follow the plan your oncology team has set for you — surveillance protocols differ meaningfully between cancers, and your team's recommendation is the one to trust."
- 🟡 **No clinical-advisory board sign-off process** for new response templates. Templates ship via PR review; clinical voices are involved informally.
- 🔴 **No formal transcript red-team review** completed by a healthcare-regulatory attorney.

**To reach perfect compliance:**
- Engage healthcare-regulatory counsel for a transcript review across Stage IIIB, Stage IV, NHL, pancreatic, and metastatic-melanoma representative chats. These are the highest-personalization cases.
- Stand up a clinical advisory board with at least one oncologist + one mental-health clinician. Their sign-off becomes part of the PR template for any prompt or overlay change.
- Add a per-response "this is general education for your context, not a specific recommendation" inline footer that the LLM cannot edit out (we already do this — make it part of every persona's required output, not just enforced by post-process).

---

### 6. FDA SaMD — EDGE CASE

**May 8 finding:** Fits the CDS exemption narrowly. PRO-CTCAE alerts + survivorship schedules could be argued the other direction.

**Current state:**
- ✅ ClinicalTrials.gov matching is presented as search/match, never as recommendation.
- ✅ Surveillance schedules defer to oncology team explicitly.
- 🔴 **No PRO-CTCAE Grade 3+ escalation logic exists** ([lib/profile_utils.py:485](lib/profile_utils.py#L485) handles grade display but no structured alerting). This is paradoxically a *defense* against SaMD classification — we don't direct clinical action.
- 🔴 **No formal "WondrChat is not a regulated device" memo** documenting the CDS-exemption position.

**To reach perfect compliance:**
- Have counsel draft + sign the non-device determination memo so the position is documentable.
- If PRO-CTCAE escalation is ever added, design it from the start to direct users to their provider — never to a specific clinical action (e.g., "this is severe — call your oncology team today" is safe; "stop your medication" is not).
- Monitor FDA's CDS exemption guidance quarterly. Add a watch entry to the compliance review cadence.

---

### 7. State Comprehensive Privacy Laws (CCPA, VCDPA, CPA, etc.) — PARTIAL

**May 8 finding:** Privacy Policy mentions CCPA but is missing sensitive-PI limit mechanism, GPC honoring, DPIA, service-provider contract terms.

**Current state:**
- ✅ Privacy Policy covers CCPA, GDPR, MHMDA ([public/index.html:6439-6530](public/index.html#L6439)).
- ✅ GPC header detection and honoring at [api/index.py:58-64](api/index.py#L58).
- ✅ Full DPIA at [docs/compliance/dpia.md](docs/compliance/dpia.md):
  - Per GDPR Article 35 + CO/VA/CT/TX requirements
  - Risk register: re-identification, sub-processor breach, insider misuse, hallucination, user mis-disclosure, state enforcement, consent loss ([lines 49-60](docs/compliance/dpia.md#L49))
  - Lawful basis: Article 6(1)(b) + 9(2)(a) ([lines 36-39](docs/compliance/dpia.md#L36))
  - Final decision: low-to-medium residual risk
  - Quarterly review cadence
- ✅ Sub-processor list with retention claims at [docs/compliance/subprocessor_chain.md](docs/compliance/subprocessor_chain.md).
- 🟡 **CCPA "Limit Use of Sensitive Personal Information"** mechanism is functionally satisfied (we don't use cancer diagnosis for advertising or sale) but is not surfaced as a user-facing affordance. A user clicking "Limit Use" today would see no behavioral change; the spec arguably requires the affordance even if it's a no-op.
- 🟡 **Universal privacy law block** — Policy mentions CCPA + GDPR + MHMDA but not the full 19-state block (VA, CO, CT, UT, IA, IN, TN, TX, OR, MT, DE, NH, NJ, KY, RI, MN, MD, NE). Most have similar enough rights that the existing language covers them, but the policy should name them explicitly.

**To reach perfect compliance:**
- Update the Privacy Policy to enumerate the full 19-state block + the rights each grants. Reuse the same affordances (access / deletion / portability / appeal) since they're already implemented.
- Add a "Limit Use of Sensitive Personal Information" link in the user account settings even though it's a no-op operationally.
- Move the DPIA quarterly review onto a calendar — easy to let slip.
- Document service-provider contract terms per CCPA in the sub-processor chain doc once DPAs are signed.

---

### 8. GDPR / UK GDPR — APPLIES IF EU/UK USERS

**May 8 finding:** Lawful basis, DPO/Representative, Article 30 RoPA, SCCs all absent. Vague retention.

**Current state:**
- ✅ Lawful basis documented in DPIA ([lines 36-39](docs/compliance/dpia.md#L36)): Article 6(1)(b) contract + 9(2)(a) explicit consent.
- ✅ Three-checkbox consent at signup satisfies "explicit consent" under Article 9.
- ✅ Privacy contact: privacy@wondrlinkfoundation.org.
- 🔴 **No Article 30 RoPA** (Record of Processing Activities) document.
- 🔴 **No designated EU Representative** (Article 27). Required for any controller offering services to EU residents without an EU establishment.
- 🔴 **No Standard Contractual Clauses (SCCs)** documented for transfers to Together AI / Groq / Vercel / Supabase (all US-based).
- 🟡 Retention language is still vague.

**To reach perfect compliance:**
- **Strategic decision first:** allow EU/UK users at launch or geofence them out. The GDPR build is real work; if EU demand is unclear, geofence and revisit when there's a business case.
- If allowing EU users:
  - Draft Article 30 RoPA.
  - Appoint an EU Representative (third-party services exist for ~€500–1,500/year).
  - Include SCCs in every DPA with US sub-processors.
  - Replace vague retention language with concrete periods.

---

### 9. EU AI Act — IF EU USERS

**May 8 finding:** Transparency obligations apply regardless of risk classification. Medical-device classification triggers high-risk regime (effective 2026-08-02).

**Current state:**
- ✅ AI disclosure satisfies the transparency obligation (persistent banner).
- ✅ FDA SaMD position (CDS exemption framing) carries over conceptually for the EU medical-device classification.
- 🔴 No formal EU AI Act risk-classification memo.

**To reach perfect compliance:**
- Tied to the EU strategic decision above. If EU users in, document the limited-risk classification and the transparency obligation compliance.
- If high-risk classification ever attaches (i.e., a clinical partnership in the EU), the obligations expand dramatically. Track this.

---

### 10. ADA / WCAG 2.1 AA Accessibility — PARTIAL

**May 8 finding:** Unverified. Cancer patients are disproportionately likely to have disabilities affecting web use.

**Current state:**
- ✅ Semantic HTML in use throughout ([public/index.html](public/index.html)) — `role="dialog"`, `role="alertdialog"`, `role="alert"`, `role="status"`, `aria-label`, `aria-labelledby`, `aria-modal="true"`, `aria-live`.
- ✅ 44px touch targets enforced ([public/index.html ~line 3609](public/index.html#L3609)) per WCAG + Apple HIG.
- ✅ Focus management on modals (open/close trapping).
- 🔴 **No automated accessibility test** (axe, Lighthouse CI, PA11y) wired into CI.
- 🔴 **No Accessibility Statement page** on the site.
- 🔴 **No manual screen-reader audit** (NVDA / VoiceOver / JAWS) on critical paths.

**To reach perfect compliance:**
- Wire `npx playwright test` with `@axe-core/playwright` (or PA11y) into CI. Block PRs on accessibility regressions in the chat / signup / profile / screenings / deletion flows.
- Run a manual screen-reader pass on those same flows. Document the results.
- Add an Accessibility Statement page linked from the footer with the WCAG target level, known issues, and a contact path.

---

### 11. COPPA / Age Verification — PARTIAL

**May 8 finding:** Unverified.

**Current state:**
- ✅ Explicit 18+ checkbox at signup. Server-side validation in [lib/compliance.py:106-110](lib/compliance.py#L106).
- ✅ Terms of Use restricts to 18+.
- 🟡 Self-declaration only — no date-of-birth picker.

**To reach perfect compliance:**
- Add a DOB picker (year ≤ current year - 18). This is the conservative bar for any product that touches health data and pediatric oncology context.
- Decide policy for the 13–17 pediatric oncology cohort. Cleanest path remains 18+ only.

---

### 12. AI Disclosure / Transparency — PRESENT

**May 8 finding:** Inside the chat UI itself, AI nature isn't reinforced visually.

**Current state:**
- ✅ Persistent banner at [public/index.html:7264-7266](public/index.html#L7264): "You're chatting with an AI assistant — not a person, not medical advice. AI can make mistakes; please verify important information with your care team."
- ✅ Bot avatar uses the WondrLink logo with brand-50 framing — distinct from a human profile photo.
- ✅ Consent modal explicitly names "AI providers (Together AI, Groq)."
- ✅ Welcome modal text confirms AI nature.

**To reach perfect compliance:**
- Add a one-line "You're chatting with an AI" reminder at the start of each *session* (not just first-run). Today's banner is persistent but visually quiet; on a fresh session a small inline "Session started — you're chatting with an AI" line in the message stream would be unmissable.
- Add a tooltip or hover state on the avatar that surfaces "AI assistant" for screen readers + keyboard users.

---

## Pre-Launch Critical Path — Current State

### Tier 1 (block launch) — 7 of 10 complete

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Engage healthcare-privacy attorney | 🔴 Not started | Highest-priority remaining item |
| 2 | Separate Consumer Health Data Privacy Notice | ✅ Shipped | [public/index.html:6338](public/index.html#L6338) |
| 3 | Separate opt-in consent for collection AND sharing | ✅ Shipped | [public/index.html:6312](public/index.html#L6312) + [lib/compliance.py:74](lib/compliance.py#L74) |
| 4 | Incident Response Plan with FTC HBNR notification path | ✅ Shipped | [docs/compliance/incident_response_plan.md](docs/compliance/incident_response_plan.md) |
| 5 | Age gate (18+) at signup | ✅ Shipped | Self-declaration; recommend DOB picker for "perfect" |
| 6 | Persistent AI disclosure in chat UI | ✅ Shipped | [public/index.html:7264](public/index.html#L7264) |
| 7 | State geo-restrictions (IL, NV minimum) | ✅ Shipped | [lib/compliance.py:28-34](lib/compliance.py#L28). WA covered by MHMDA compliance instead of geofence. |
| 8 | Verify deletion flows through to Together AI / Groq | 🟡 Partial | Local deletion shipped; vendor cascade depends on signed DPAs |
| 9 | Sign DPAs / BAAs with Supabase, Together AI, Groq, Vercel | 🔴 Not started | **Critical path** |
| 10 | Terms of Use prohibits users under 18 | ✅ Shipped | [public/index.html ToU modal](public/index.html) |

### Tier 2 (within 30 days post-launch) — 2 of 7 complete

| # | Item | Status |
|---|---|---|
| 1 | Comprehensive multi-state privacy law update | 🟡 Policy covers CCPA + MHMDA explicitly; needs 19-state enumeration |
| 2 | Global Privacy Control (GPC) honoring | ✅ Shipped ([api/index.py:58-64](api/index.py#L58)) |
| 3 | DPIA/PIA documentation | ✅ Shipped ([docs/compliance/dpia.md](docs/compliance/dpia.md)) |
| 4 | WCAG 2.1 AA accessibility audit + Statement | 🔴 Not started |
| 5 | EU/UK strategy decision | 🔴 Not made |
| 6 | Documented appeal process with 45-day SLA | ✅ Shipped (in IRP) |
| 7 | Cyber liability + tech E&O insurance | 🔴 Not procured |

### Tier 3 (ongoing) — 0 of 4

| # | Item | Status |
|---|---|---|
| 1 | State AI law tracker | 🔴 Not running |
| 2 | Quarterly compliance review with counsel | 🔴 Not scheduled |
| 3 | Clinical advisory board sign-off process | 🔴 Not stood up |
| 4 | Transcript red-team review (UPM risk) | 🔴 Not started |

---

## Recommended Path to "Perfect Compliance"

Sequencing matters — some items unblock others.

### Week 0 (now): unblock the gating items
1. **Engage healthcare-privacy attorney.** Until counsel reviews the DRAFT policies, the rest of the work is at risk of needing rework. Provide them this document + the audit findings + the source policies.
2. **Procure cyber liability + tech E&O insurance.** Underwriters will ask compliance-state questions; have this document ready.
3. **Begin DPA / BAA negotiations** with Supabase, Together AI, Groq, Vercel. Supabase HIPAA-tier BAA is the easiest. Together AI / Groq business plans for BAA support need a paid-tier upgrade decision.

### Weeks 1–2: counsel-dependent finalization
4. Counsel signs off on the not-a-Covered-Entity memo + the FDA non-device memo.
5. Counsel reviews + finalizes Privacy Policy, Consumer Health Data Privacy Notice, Terms of Use, Incident Response Plan, DPIA, Sub-processor Chain.
6. Counsel does an initial transcript red-team review across representative chats.
7. Replace all DRAFT — ATTORNEY REVIEW REQUIRED banners once review is complete.

### Weeks 2–3: engineering polish toward "perfect"
8. Add DOB picker at signup (replacing the 18+ checkbox).
9. Add CSP header to vercel.json (whitelist cdn.jsdelivr.net, fonts.googleapis.com, fonts.gstatic.com, unpkg.com, the Supabase domain).
10. Add `@axe-core/playwright` accessibility tests + an Accessibility Statement page.
11. Add the "Limit Use of Sensitive Personal Information" no-op affordance to user account settings.
12. Enumerate the full 19-state block + their granted rights in the Privacy Policy.
13. Strategic decision on EU/UK users. If in, build Article 30 RoPA + appoint EU Representative + add SCCs. If out, geofence at signup and document the decision.
14. Add per-session "you're chatting with an AI" message in the chat stream (in addition to the persistent banner).

### Week 4: launch readiness
15. Tabletop the Incident Response Plan with the named IC + Privacy Officer + counsel.
16. Sign Supabase BAA + Together AI / Groq / Vercel DPAs.
17. Spot-check the deletion cascade against each sub-processor's deletion API.
18. Begin transcript red-team round 2 (post-counsel-feedback edits).
19. Final pre-launch compliance review meeting — counsel + clinical advisor + eng lead. Sign off on launch.

### Ongoing after launch
20. State AI law tracker → calendar review monthly during 2026 (FL, MA, NH, NY, OH, PA, NJ, NC, TX are active per current trackers).
21. Quarterly DPIA review.
22. Clinical advisory board sign-off process becomes part of the PR template for any prompt or overlay change.
23. Sub-processor reviews each renewal cycle.

---

## What Changed vs. the May 8 Assessment

The May 8 review estimated a "4–6 week pre-launch sprint" was needed for Tier 1. As of 2026-05-20:

- 7 of the 10 Tier 1 items have shipped in code.
- The 3 outstanding items are all **external dependencies** (counsel, insurance underwriter, vendor legal teams), not engineering work.
- DPIA, IRP, and Sub-processor Chain are documented at attorney-review-ready quality.
- The MHMDA major-gap call from the assessment has been substantially closed; what remains is the vendor-DPA flow-through obligation, which is contractual.
- The state AI mental-health risk is now mitigated by hard signup-blocking for IL/NV + system-prompt-level forbidden-language rules + crisis short-circuit.

**Bottom line:** The product is closer to launchable than the May 8 review suggested — but the gating items are now legal/contractual rather than technical. Engineering can keep polishing the Tier 2 + Tier 3 items in parallel; the launch date is bounded by counsel turnaround and DPA signature timelines.

---

## Files Referenced

- [docs/compliance/incident_response_plan.md](docs/compliance/incident_response_plan.md)
- [docs/compliance/dpia.md](docs/compliance/dpia.md)
- [docs/compliance/subprocessor_chain.md](docs/compliance/subprocessor_chain.md)
- [docs/compliance/hbnr_breach_notification_template.md](docs/compliance/hbnr_breach_notification_template.md)
- [lib/compliance.py](lib/compliance.py) — state restrictions, consent + age validation
- [lib/deidentify.py](lib/deidentify.py) — de-identification before LLM
- [lib/confidence.py](lib/confidence.py) — crisis short-circuit
- [lib/prompts/base.py](lib/prompts/base.py) — system-prompt language rules
- [lib/surveillance.py](lib/surveillance.py) — per-cancer surveillance rubrics
- [lib/rate_limit.py](lib/rate_limit.py) — Supabase-backed rate limiter
- [api/index.py](api/index.py) — Flask endpoints (signup, chat, feedback, delete_account, GPC detection)
- [public/index.html](public/index.html) — signup modal, Privacy Policy, Consumer Health Data Notice, Terms of Use, AI banner, age gate, chat UI
- [vercel.json](vercel.json) — security headers (CSP still absent)

---

*This document is a snapshot for engineering planning and counsel briefing. The DRAFT — ATTORNEY REVIEW REQUIRED disclaimers on the in-product policies and the docs/compliance/ files remain in force until counsel review is complete.*
