# WondrChat Mobile — Submission Runbook

A linear pre-submission checklist for getting WondrChat onto the App Store and
Google Play Store. Owned by the WondrLink Foundation engineering team.

---

## Before you start

These cannot be automated — confirm each is done.

- [ ] **Apple Developer Program enrollment** as WondrLink Foundation
      (organization, not personal). Requires a D-U-N-S number; takes
      1–3 weeks the first time.
- [ ] **Google Play Console** organization account ($25 one-time).
- [ ] **Bundle identifier confirmed**: currently `org.wondrlink.wondrchat`.
      Change before the first build if the foundation prefers a different
      reverse-domain.
- [ ] **Privacy Policy URL** is live at `wondrlinkfoundation.org/privacy`.
- [ ] **Terms of Use URL** is live at `wondrlinkfoundation.org/terms`.
- [ ] **Consumer Health Data Privacy Notice URL** is live at
      `wondrlinkfoundation.org/health-data-privacy` (or equivalent — the
      in-app notice still works for review, but stores want a URL too).
- [ ] **Support email** is live: `support@wondrlinkfoundation.org`.
- [ ] **Attorney review** of the three DRAFT documents (Privacy, Terms,
      Health-Data Notice) is complete — strip the DRAFT banners after.
- [ ] **Supabase HIPAA tier** + **Together AI DPA** + **Groq DPA** + **Vercel
      DPA** are all signed.
- [ ] **Cyber liability + tech E&O insurance** is procured.

---

## Build setup

```bash
cd mobile
npm install -g eas-cli
eas login                       # uses your Expo account
eas build:configure             # links the slug to an Expo project (1-time)
```

Fill `app.json` `expo.extra`:

```json
"extra": {
  "apiBase": "https://wondrlink-chat.vercel.app",
  "supabaseUrl": "https://YOUR-PROJECT.supabase.co",
  "supabaseAnonKey": "eyJhbG...",
  "sentryDsn": "https://...@sentry.io/..."
}
```

Or alternately set these as EAS secrets:

```bash
eas secret:create --scope project --name SUPABASE_URL --value "https://..."
eas secret:create --scope project --name SUPABASE_ANON_KEY --value "eyJ..."
eas secret:create --scope project --name SENTRY_DSN --value "https://..."
```

Fill `eas.json` `submit.production.ios` with your Apple ID, ASC App ID, and
Apple Team ID. Drop the Play Console service-account JSON at
`mobile/play-store-key.json` (gitignored — verify your `.gitignore` covers it).

---

## Compliance / safety checklist (App Store reviewers WILL check)

- [ ] **Onboarding cannot be bypassed.** Fresh install → cannot reach the
      chat without completing age + state + 3 MHMDA consents.
- [ ] **Blocked-state soft-deactivation works.** Pick "Nevada" during sign-up
      → state-restricted screen appears with sign-out + delete-account
      options.
- [ ] **Consent version bump re-prompts.** Force-bump `CURRENT_CONSENT_VERSION`
      on the server, restart mobile → re-consent flow triggers.
- [ ] **Crisis keyword guardrails fire.** Type "I'm having chest pain" → modal
      shows BEFORE the message hits `/api/chat`. Tap Call 911 → dialer opens.
- [ ] **Self-harm path puts 988 first.** Type "I want to hurt myself" → modal
      shows; 988 helpline appears at the top of the list.
- [ ] **PHQ-9 crisis backstop.** Take a PHQ-9 with Q9 ≥ 1 → backend returns
      `is_crisis: true` → mobile shows the crisis modal with 988/Crisis
      Text/911.
- [ ] **Help tab is always 1 tap away** with 911/988/741741 tap-to-call.
- [ ] **Sources render on bot responses.** Send a chat message → the response
      card shows an expandable Sources section.
- [ ] **Per-message disclaimer footer** is visible under every bot response.
- [ ] **Persistent AI banner** sits at the top of the Chat screen.
- [ ] **Privacy/Terms/Health-Notice screens** reachable from Settings; URLs
      open the live wondrlinkfoundation.org pages.
- [ ] **Delete Account** double-confirms (checkbox + typed `DELETE`) and
      successfully removes the account.
- [ ] **No crashes** in a 30-minute exploratory test session.
- [ ] **VoiceOver / TalkBack** pass: every Pressable has a role + label,
      icons aren't read out as "image".

---

## Build + ship

### iOS

```bash
eas build --platform ios --profile production
# wait ~15–25 min
eas submit --platform ios
```

In App Store Connect:
- App description: lead with informational nature ("WondrChat is an
  informational guide for people navigating colon cancer…"). Avoid the words
  "diagnose", "treat", or "cure" in title or subtitle.
- **Privacy Nutrition Labels**: declare Together AI + Groq + Supabase as
  third-party data processors. Declare health-data collection.
- **Age rating**: 17+ (health-data app).
- Privacy Policy URL, Terms URL, Support URL — all live.
- Screenshots: 6.7", 6.5", 5.5" iPhone sizes. Capture from a real device after
  signing in with a test account on the production build.

### Android

```bash
eas build --platform android --profile production
eas submit --platform android
```

In Play Console:
- Data safety form: declare same processors as iOS.
- Sensitive permissions: none should be requested at runtime.
- Internal-testing track first; promote to production after a week of
  successful tester runs.

---

## After launch

- [ ] Monitor Sentry for crash spikes (especially during the first 48h).
- [ ] Watch for in-app feedback submissions and respond.
- [ ] Schedule the annual tabletop exercise of the incident response plan
      (see `docs/compliance/incident_response_plan.md`).
- [ ] Tag the deployment as `mobile-v1.0.0-launch` for audit history.

---

## Useful EAS commands

```bash
# Track builds
eas build:list

# View a specific build's logs
eas build:view BUILD_ID

# Iterate on production code without a new build (OTA update — JS only)
eas update --branch production --message "fix typo in disclaimer"

# Rollback an OTA update
eas update --branch production --message "rollback" --republish --group GROUP_ID
```
