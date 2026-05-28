# Internal Testing Kickoff — TestFlight + Play Internal

**Goal:** put a real native build of WondrChat in front of you (and a small handful of trusted testers) without going through Apple/Google review. This is the intermediate step between "Expo Go demo on Siva's phone" and "public App Store release."

**What internal testing is NOT:** public release. Apple TestFlight Internal Testing and Google Play Internal Testing tracks bypass review. Only people you explicitly invite by email can install the app.

---

## Status as of 2026-05-25

**Code is in good shape for an internal binary.** Every feature works under Expo Go (dev mode). What we haven't validated yet:
- The app compiles cleanly as a real native binary via EAS Build.
- Native modules (datetimepicker, sentry, clipboard, async-storage, supabase, reanimated) behave the same in release mode.
- End-to-end real-device smoke (auth → consent → chat → cancer switch → wellness → care → settings).

The first `eas build` will surface any compatibility issues. Those are usually fixed in <30 min each.

---

## Deferred items (intentionally NOT in this internal release)

These stay on the roadmap and don't block internal testing, but they DO block public store release. Tracking them here so nothing falls through the cracks.

### Engineering — fast follow-ups
- **Voice transcription** — mic button currently shows a "coming soon" alert. Needs a `/api/transcribe` backend endpoint (Whisper) + replace the alert with `expo-av` recording. ~half a day.
- **"Discard changes?" confirmation in profile wizard** — header-back at step 4 silently drops unsaved edits. Small dialog.
- **Voice dictation in Visit Recap** — desktop has it; mobile doesn't. Same backend dependency as above.

### Operational — waiting on Foundation
- **Production SMTP** — set up Resend (or similar) so signup confirmation emails actually deliver. Doc exists at `docs/deployment/email-smtp-setup.md`.
- **Production vs staging environment separation** — currently both Expo Go and the eventual binary hit the same Supabase project + Vercel deployment. Should be split before public release.
- **Healthcare-privacy attorney engagement + signed DPAs + named IC/Privacy Officer + insurance** — all the compliance items tracked in `docs/compliance/compliance_response_2026-05-20.md`.
- **DRAFT — ATTORNEY REVIEW REQUIRED banners** on Privacy/Terms/Health-Notice screens stay until counsel ratifies.

### App Store / Play Store metadata (needed for PUBLIC release, not internal)
- Privacy nutrition labels (Apple) + Data safety form (Google) — must explicitly disclose Together AI + Groq receiving de-identified queries.
- Screenshots for 6.7" + 6.1" iPhone, 13" iPad, Android phone.
- Description + keywords + support URL.
- Age rating questionnaire — be honest about PHQ-9 / GAD-7 mental health content.

### Roadmap
- Expo SDK 55 upgrade — planned after parity ships + first round of real-device feedback.

---

## The internal testing pipeline

Three phases. Phase A is one-time setup. Phases B and C run for every build.

### Phase A — one-time setup

**A1. EAS login.** Run this on your machine once. EAS is the Expo build service that compiles native binaries on its servers.

```bash
cd /Users/sivapichappan/WondrLink-Chat/mobile
eas login
```

You'll be prompted for your Expo account credentials. If you don't have one yet, go to https://expo.dev and create a free account first.

**A2. Create app records in both stores.** A "record" is just a placeholder app entry the stores use to identify uploads.

- **App Store Connect**: https://appstoreconnect.apple.com → My Apps → **+** → New App
  - Platform: iOS
  - Name: `WondrChat`
  - Primary Language: English (U.S.)
  - Bundle ID: select `org.wondrlink.wondrchat` (you may need to register this bundle ID first at https://developer.apple.com/account/resources/identifiers/list — let me know if you do)
  - SKU: anything unique, e.g. `wondrchat-ios-001`
  - User Access: Full Access
- **Google Play Console**: https://play.google.com/console → Create app
  - App name: `WondrChat`
  - Default language: English (United States)
  - App or game: App
  - Free or paid: Free
  - Declarations: agree to the policies (these are honest-to-fill checkboxes)

**A3. Generate API credentials for each store.** This is what EAS uses to upload builds without you typing your password each time.

- **Apple — App Store Connect API Key:**
  1. https://appstoreconnect.apple.com → Users and Access → Integrations → App Store Connect API → **Generate API Key**
  2. Name it `EAS Submit` (or anything)
  3. Access: **App Manager**
  4. Click Generate. **Download the .p8 file immediately** — it's only downloadable once.
  5. Note the **Key ID** and **Issuer ID** (visible on the same screen).
  6. Place the .p8 file somewhere you'll remember (e.g. `~/Documents/WondrChat-keys/`). Don't commit it to git.
- **Google — Play Service Account JSON:**
  1. https://console.cloud.google.com → IAM & Admin → Service Accounts → Create Service Account.
  2. Name: `eas-play-submit`. Skip role assignment.
  3. After creation: Keys tab → Add Key → JSON → download.
  4. https://play.google.com/console → Users and permissions → Invite new users → paste the service account email → grant "Admin (all permissions)" for this app.
  5. Place the JSON next to the .p8 file. Don't commit.

**A4. Fill in `eas.json` submit credentials.** I'll do this once you give me:
- Your Apple ID email
- Your 10-character Apple Team ID (visible at https://developer.apple.com/account)
- The ASC App ID (numeric, visible in the app record's URL after you create it)
- Path to the Play service-account JSON

---

### Phase B — every build cycle

I run these. You watch.

```bash
# iOS first
cd mobile
eas build --profile production --platform ios
# ~15-30 min wait
eas submit --profile production --platform ios --latest

# Android next
eas build --profile production --platform android
eas submit --profile production --platform android --latest
```

`eas build` compiles on Expo's servers and returns a `.ipa` / `.aab` URL.
`eas submit` uploads it to TestFlight / Play Internal automatically.

---

### Phase C — invite testers

- **TestFlight Internal Testing:** ASC → your app → TestFlight → Internal Testing → add testers by Apple ID email. They get a link to install the TestFlight app + your build within minutes (no Apple review).
- **Play Internal Testing:** Play Console → your app → Testing → Internal testing → create a tester list → add Gmail addresses. They get an opt-in link.

Initial tester list (recommend keeping it small for v1):
- You
- Your supervisor / a Foundation contact
- 1-2 trusted clinical reviewers

After installation, walk through the smoke checklist in [docs/deployment/internal-testing-kickoff.md#smoke-checklist](#smoke-checklist).

---

## What I need from you, in order

| # | Action | Effort | Blocks |
|---|---|---|---|
| 1 | Run `eas login` on your machine | 2 min | everything |
| 2 | Tell me when done (paste output of `eas whoami`) | — | step 3 |
| 3 | Confirm your Expo account email | — | step 4 |
| 4 | While I prep the iOS build, you start Phase A2 (create app records) | 30 min | Phase B's `eas submit` |
| 5 | Generate ASC API Key + download .p8 → tell me Key ID + Issuer ID + file path | 10 min | iOS submit |
| 6 | Set up Play service account + download JSON → tell me file path | 15 min | Android submit |

You don't need to do all of this in one sitting. The build step (Phase B) only depends on step 1.

---

## What I will do

- Pre-flight check: verify `app.json` icon + splash + permissions strings, `eas.json` production profile.
- Run `eas build --profile production --platform ios` and watch the build.
- Fix any native-module compat issues that surface.
- Run `eas submit` once you have ASC credentials.
- Repeat for Android.
- Help you debug the first install on a real device.

---

## Costs

- Apple Developer Program: $99/year — Foundation already pays this.
- Google Play Developer account: $25 one-time — Foundation already pays this.
- EAS Build: **free tier** gives 30 builds/month, which is plenty for internal cycles. Paid plan ($29/month) gives priority + more concurrent builds, not needed yet.

---

## Timeline estimate

| Day | What happens |
|---|---|
| 1 (today) | A1–A3 setup, Phase B first iOS build, iterate on any native-module surprises |
| 2 | First TestFlight upload, you install on iPhone, smoke test |
| 3 | First Play Internal build + install on Android |
| 4+ | Iterate based on real-device feedback; new build whenever code changes |

---

## Smoke checklist

For each new internal build, walk through this on a real device:

1. Cold launch → splash → auth screen
2. Sign up with a fresh email → confirm via email (note: SMTP not in prod yet, so check Supabase dashboard for the link if email doesn't arrive)
3. Onboarding → DOB → state → 3 consents → "Continue"
4. Land on chat tab → confirm cancer pill in header
5. Tap cancer pill → switch cancer → "Switch focus" → conversation clears
6. Send a chat message → AI response renders with sources + follow-ups + feedback buttons
7. Tap a follow-up chip → second response renders
8. Trash icon → "Clear conversation?" → confirm
9. Care tab → wellness card → PHQ-9 → answer 9 questions → save
10. Tools tab → Trends → see the PHQ-9 line
11. Tools tab → Saved trials → empty state OK
12. Care tab → "View your profile" → wizard → enter basics → Save → returns to profile
13. Settings tab → Detail level → switch to Detailed → back to chat → next response is longer
14. Settings tab → Consent management → withdraw sharing → chat input disables + banner shows → restore → chat input re-enables
15. Settings tab → Delete account flow (type "DELETE" → confirm → signs out)

If anything in 1-15 breaks, that's a regression to fix before inviting other testers.
