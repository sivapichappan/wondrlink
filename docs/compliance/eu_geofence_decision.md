# EU / EEA / UK / Switzerland Geofence — v1 Decision

**Status:** ACTIVE for v1 public launch
**Effective:** 2026-05-20
**Owner:** Engineering + Privacy Officer (pending counsel sign-off)
**Reversibility:** Revisit when a business case justifies the EU compliance build (see "What it would take to lift the geofence" below).

> ⚠️ **DRAFT — ATTORNEY REVIEW REQUIRED.** This decision document records engineering's conservative posture and the reasoning behind it. Counsel should review and either ratify or override before public launch.

## Decision

WondrLink v1 **does not serve** residents of:
- All 27 EU member states
- EEA additions (Iceland, Liechtenstein, Norway)
- United Kingdom
- Switzerland

Signups originating from these regions receive **HTTP 451 ("Unavailable For Legal Reasons")** with a user-facing modal explaining that we're not yet able to offer service in the region and that we will revisit once compliance work is complete.

## Why

Serving EU/EEA/UK/Swiss users requires:

1. **GDPR Article 30 Records of Processing Activities** — formal, auditable, kept current.
2. **GDPR Article 27 EU Representative** — a designated EU-based legal entity that acts as our point of contact for data subjects and supervisory authorities. Third-party services exist (~€500–1,500/year); the choice is contractual, not engineering.
3. **Standard Contractual Clauses (SCCs)** in every sub-processor contract for US-based vendors (Supabase, Together AI, Groq, Vercel). Today, none of our DPAs include SCCs.
4. **EU AI Act risk-classification memo** — limited-risk transparency obligations at minimum; high-risk (medical-device) classification triggers a substantially expanded set of obligations effective August 2026.
5. **UK GDPR + UK Data Bridge / IDTA** mechanisms for UK-resident data subjects.
6. **Concrete retention periods** (already done — Task 5 in the May-2026 final-push) but in EU-recognized form.
7. **A DPO determination** — likely required given health-data processing scale, even though we currently process well under any threshold that makes it mandatory.

None of these are technically hard; collectively they're 4–6 weeks of focused legal + engineering work. For v1 we lack:
- Time to do them properly before the launch window.
- Validated EU demand to justify the work.
- A signed DPA chain that includes SCCs.

The conservative posture is to launch US-only and revisit when business demand or partnership opportunity drives the work.

## How (implementation)

- **Detection:** server-side, via the CDN-supplied `x-vercel-ip-country` request header. Client-side IP is never trusted.
- **Library:** [lib/compliance.py](../../lib/compliance.py) — `BLOCKED_COUNTRIES`, `detect_country_code()`, `is_blocked_country()`, `validate_country()`.
- **Enforcement points:**
  - [api/index.py `/api/auth/register`](../../api/index.py) — best-effort early reject (registration is largely handled by Supabase Auth on the client today, so this catches the rare case of a direct API hit).
  - [api/index.py `/api/save_acknowledgement`](../../api/index.py) — authoritative reject. Every new user goes through this on first login; this is the actual choke point.
- **Frontend:** [public/index.html](../../public/index.html) `saveAcknowledgement()` handles HTTP 451 → reuses `showStateRestrictedModal()` with the geofence explanation copy.
- **Privacy Policy:** updated to remove the explicit GDPR rights promise and to note the geofence in place of an outdated EU/EEA rights line.
- **ToU:** Eligibility section now lists the EU/EEA/UK/Swiss exclusion alongside the IL/NV state restriction.

## What about existing EU users?

The product is pre-launch and is not currently serving EU users. There is no migration step.

If any test or beta accounts originate from blocked regions, they should be soft-deactivated through the existing state-restricted flow + manual review before public launch.

## What it would take to lift the geofence

In rough sequence:

1. **Strategic decision** — business case validated; resources committed.
2. **GDPR Article 30 RoPA** drafted and maintained quarterly.
3. **EU Representative appointed** — engage a service provider (DataRep, Prighter, EDPB-registered firms).
4. **DPAs renegotiated** with all sub-processors to include SCCs (Module 2 controller→processor or Module 3 processor→sub-processor, as applicable).
5. **EU AI Act risk-classification memo** signed by counsel.
6. **DPO determination** documented (and, if required, appointed).
7. **Retention periods reviewed** under EU principles — already concrete since Task 5; just needs counsel ratification.
8. **Cookie / consent banner** review — we don't currently use non-essential cookies, but any analytics added before EU launch would need explicit prior consent.
9. **Privacy Policy + Consumer Health Data Notice** localized — at minimum into the user's selected language; ideally with regional sections.
10. **Lift the geofence** in [lib/compliance.py](../../lib/compliance.py) — remove the entry from `BLOCKED_COUNTRIES` and update the 451 modal copy.

Estimated effort: 4–6 weeks engineering + counsel turnaround.

## Trigger to revisit

- A clinical or research partnership with an EU-based oncology institution wants WondrLink available to their patients.
- An advocacy partnership requires multi-jurisdiction coverage.
- Validated organic demand from EU patients (track 451 hits in the CSP-report-style log to quantify).
- A regulatory shift makes the build cheaper (e.g. EU-US Data Privacy Framework expansion, simpler SCC alternatives).

## Open items

- [ ] Counsel ratifies this decision and removes the DRAFT banner.
- [ ] Add a 451-hit counter (anonymous) so we can quantify the demand we're declining.
- [ ] Decide on a sign-up waitlist for EU users wanting to be notified when we launch (would itself require a minimal GDPR processing record).

---

*Linked decisions:* [docs/compliance/dpia.md](dpia.md) · [docs/compliance/subprocessor_chain.md](subprocessor_chain.md) · [docs/compliance/incident_response_plan.md](incident_response_plan.md)
