# WondrChat mobile

React Native (Expo SDK 54, TypeScript) client for WondrChat — talks to the
existing Flask backend in `../api/` via the user's Supabase JWT.

## Get started

```bash
cd mobile
npm install
npx expo start
```

Then either `i` to open in iOS simulator, `a` for Android, or scan the QR code
with Expo Go on a physical device.

## Required config before first run

Open `app.json` and fill in `expo.extra`:

```json
"extra": {
  "apiBase": "https://wondrlink-chat.vercel.app",
  "supabaseUrl": "https://YOUR-PROJECT.supabase.co",
  "supabaseAnonKey": "eyJhbG...",
  "sentryDsn": ""
}
```

These can also be overridden at runtime via `EXPO_PUBLIC_*` env vars
(e.g. `EXPO_PUBLIC_SUPABASE_URL`).

## Project layout

```
mobile/
├── app/                   # Expo Router screens (file-based)
│   ├── (auth)/            # welcome / login / register (pre-session)
│   ├── (onboarding)/      # consent / disclaimer / state-restricted
│   ├── (tabs)/            # Chat · Care · Tools · Help · Settings
│   ├── tools/             # Care-tool detail screens (PHQ-9, trials, etc.)
│   ├── settings/          # Sub-screens (privacy, terms, delete-account, …)
│   └── profile.tsx
├── components/            # UI primitives + chat/care/common
├── hooks/                 # useAuth, useAcknowledgement, useChat, useCare
├── lib/
│   ├── api/               # Per-domain fetch wrappers
│   ├── safety/            # Client-side crisis keyword guardrails
│   ├── env.ts, supabase.ts, query.ts, sentry.ts
├── constants/theme.ts     # Brand tokens
├── global.css             # NativeWind entry
└── tailwind.config.js
```

Shared TypeScript types and disclaimer copy live in `../shared/`. See that
folder's README for the sync rules with the Python source of truth.

## Auth flow

Auth uses the backend's `/api/auth/*` endpoints (rate-limited) which return
Supabase JWTs. We then plug those into `supabase.auth.setSession` so
AsyncStorage persists the session and every other request carries the JWT
via the `Authorization: Bearer` header.

## Compliance flow

1. Welcome → Sign up → Backend creates the Supabase user
2. Root layout GETs `/api/check_acknowledgement`
3. If `needs_consent` → onboarding/consent screen (age + state + 3 MHMDA consents)
4. Submit posts `/api/save_acknowledgement`. 422 → state-restricted screen.
5. Otherwise → main tabs.

Consent version is `v2-mhmda-2026-05`. When the server-side
`CURRENT_CONSENT_VERSION` (`lib/compliance.py`) bumps, mobile re-prompts on
next launch.

## Building for stores (Phase 8)

```bash
npm install -g eas-cli
eas login
eas build:configure
eas build --platform ios --profile production
eas build --platform android --profile production
```

Bundle ID: `org.wondrlink.wondrchat`. Confirm with WondrLink Foundation
before submission.
