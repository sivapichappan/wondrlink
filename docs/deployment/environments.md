# Environments — Current State + Proposed Split for Launch

**Prepared:** 2026-05-23
**Audience:** Engineering + Supervisor (non-technical)
**Status:** Proposal — awaiting supervisor sign-off before standing up the staging stack

> Companion to the supervisor reply about clean prod-vs-staging separation. This document captures (a) what we have today, (b) why a split matters before public launch, and (c) the concrete proposal to get there.

---

## Today (single environment)

Today every part of WondrChat runs in **one** environment. There is no separate "staging" or "dev" stack — the live site and the development site are the same site.

```
┌───────────────────────────────────────────────────────────┐
│                        TODAY                              │
│                                                           │
│   Web SPA                       Mobile app (in dev)       │
│   wondrchat.vercel.app          (Expo simulator builds)   │
│         │                              │                  │
│         └──────────────┬───────────────┘                  │
│                        ▼                                  │
│              Flask API (Vercel)                           │
│              wondrchat.vercel.app/api                     │
│                        │                                  │
│                        ▼                                  │
│              Supabase project                             │
│              kgcelxfhmhymutyrorpw.supabase.co             │
│              (production data: users, profiles,           │
│               chat history, screening scores,             │
│               consent records, RAG chunks)                │
└───────────────────────────────────────────────────────────┘
```

**What this means in practice:**
- Every time we test a new feature against the real backend, we're hitting the production database.
- If we ever onboard a test user, the test profile lives in the same table as real user data.
- A schema migration applied during testing is also applied to production immediately.

This was acceptable while WondrChat had zero public users. It is **not acceptable** once we start onboarding real patients.

---

## Proposed (staging + production split)

```
┌──────────────────────────────────────────────────────────────────────┐
│                      STAGING                                         │
│                                                                      │
│  Web SPA                       Mobile (TestFlight + Play Internal)   │
│  wondrchat-staging.vercel.app  (built with --profile staging)        │
│        │                              │                              │
│        └─────────────┬────────────────┘                              │
│                      ▼                                               │
│            Flask API (Vercel)                                        │
│            wondrchat-staging.vercel.app/api                          │
│                      ▼                                               │
│            Supabase project: STAGING                                 │
│            (test users + fixture data; anyone on the team            │
│             can wipe + reseed; no PHI ever lands here)               │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                      PRODUCTION                                      │
│                                                                      │
│  Web SPA                       Mobile (App Store + Play public)      │
│  wondrchat.vercel.app          (built with --profile production)     │
│        │                              │                              │
│        └─────────────┬────────────────┘                              │
│                      ▼                                               │
│            Flask API (Vercel)                                        │
│            wondrchat.vercel.app/api                                  │
│                      ▼                                               │
│            Supabase project: PRODUCTION                              │
│            (real users; locked down; only the deploy                 │
│             pipeline writes schema changes; daily backups)           │
└──────────────────────────────────────────────────────────────────────┘
```

**Key properties:**

1. **Fully isolated data.** Staging Supabase and production Supabase are separate projects with separate databases. A test user account on staging doesn't exist in production and vice versa.
2. **Schema changes test on staging first.** Every database migration runs on staging for at least 48 hours before being applied to production.
3. **Mobile app picks its backend at build time.** The Expo build profile (`--profile staging` vs `--profile production`) injects a different API URL into the binary. No code change needed when we promote a build from staging to production.
4. **Same secret management.** Each environment has its own Supabase keys, Together AI keys, etc., all stored as encrypted Vercel + EAS secrets — never in the codebase.
5. **TestFlight + Play Internal point at staging by default** during testing; only when we're ready for App Store / Play public launch do we cut a production-pointing build.

---

## What's already done

- **Mobile app build profiles** ([mobile/eas.json](../../mobile/eas.json)) — already include `development`, `preview`, `staging`, and `production` profiles, each injecting its own `EXPO_PUBLIC_API_BASE`. As soon as the staging URL exists, the mobile pipeline is ready.
- **Env-driven API URL** ([mobile/lib/env.ts](../../mobile/lib/env.ts)) — the runtime reader already supports `EXPO_PUBLIC_API_BASE` injected at build time.
- **Bundle identifier** (`org.wondrlink.wondrchat`) — distinct from WondrVoices + WondrDrop; no conflict with the existing apps on the Foundation's developer accounts.
- **Sub-processor list + retention schedule** ([docs/compliance/subprocessor_chain.md](../compliance/subprocessor_chain.md)) — documents which vendor holds what data, so the staging-vs-production split has a clean reference point.

---

## What needs to happen (sequenced)

In order. Each step depends on the previous one being done.

| # | Step | Who | Notes |
|---|---|---|---|
| 1 | **Decide & sign off on the split** | Supervisor + Eng | This document is the proposal. 30-min meeting recommended. |
| 2 | **Create staging Supabase project** | Eng | New project under the same Supabase org; Free or Pro tier (~$25/mo if Pro is required for backups). |
| 3 | **Apply current schema + RAG chunks to staging** | Eng | Re-run migrations + seed scripts against staging. |
| 4 | **Create wondrchat-staging.vercel.app Vercel project** | Eng | Same repo, different deployment target; staging env vars point at staging Supabase. |
| 5 | **Promote engineering to staging-first workflow** | Eng | All new features merge → staging → 48h soak → production. |
| 6 | **Build mobile TestFlight against staging** | Eng (once added to dev accounts) | `eas build --profile staging --platform ios` then `eas submit --profile staging`. |
| 7 | **First internal testers** | Supervisor + Eng + clinical reviewer | Walk through staging mobile build end-to-end. |
| 8 | **Flip to production build for public launch** | Eng | `eas build --profile production` — same code, different backend. |

---

## Cost implications (rough)

| Item | Current | Proposed | Delta |
|---|---|---|---|
| Vercel | Hobby (free) | Pro ($20/mo) for staging + Pro for production | +$40/mo |
| Supabase | Free tier (1 project) | Pro ($25/mo) for staging + Pro for production | +$50/mo |
| Together AI / Groq | Pay-as-you-go | Same, but with separate API keys per env | $0 new fixed cost |
| **Total new monthly cost** | | | **~$90/mo** |

These are the standard tiers most healthcare-adjacent apps run at. Lower tiers exist but lack the daily backups + point-in-time recovery we want for the production database.

---

## Open questions for the supervisor meeting

1. Sign-off on the ~$90/mo additional infra cost? Or stay on free tiers for as long as possible (some compliance posture lost)?
2. Should the staging mobile build be installable by the broader Foundation team (e.g. 20 internal testers via TestFlight), or stay tight to engineering only?
3. Production database backup retention — Supabase Pro gives 7 days of PITR; do we want extra-paid retention for compliance defense (HBNR audit trail)?
4. Domain naming — `wondrchat.vercel.app` works today, but a custom domain (`chat.wondrlinkfoundation.org`?) would feel more polished at launch. When do we want to do that?
5. Bug tracking + on-call rotation once we're live with real users — out of scope for this doc but worth a separate conversation.

---

## Risks if we don't split before launch

- **Test data contaminates the user analytics + research data we'll want later.** We can't tell real PHQ-9 scores from internal QA scores.
- **A schema migration that breaks something is immediately visible to every user** — there's no chance to catch it in staging first.
- **Deletion of test accounts is risky** — the same SQL that wipes a test user could wipe a real one with one wrong WHERE clause.
- **App Store reviewers may flag the lack of environment separation** as part of their privacy-disclosure review, especially given health data scope.

The split is cheap enough relative to the risk that it's effectively pre-launch table stakes.
