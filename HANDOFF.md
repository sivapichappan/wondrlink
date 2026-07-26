# HANDOFF — active work

_Keep this for in-flight work only. Fold anything permanent into `.claude/CLAUDE.md`
and prune the rest. Last updated: 2026-07-26._

## IN FLIGHT RIGHT NOW

1. **Scan-report crash on build #32 — ROOT-CAUSED + fixed 2026-07-26.**
   Build #32 shipped WITHOUT the ExpoMlkitOcr native module: Expo autolinking
   **silently skips** any pod whose podspec needs a higher iOS deployment
   target than the app (ExpoMlkitOcr.podspec pins iOS **16.0**; SDK 54 default
   is 15.1) — pod install "succeeds", JS bundles, then
   `requireNativeModule('ExpoMlkitOcr')` throws when the route loads → crash.
   Proven from build #32 logs: zero ExpoMlkitOcr/GoogleMLKit lines; every
   other Expo pod installed.
   - **OTA guard PUBLISHED** (update group `fdf79cd3`, runtime 1.1.0, iOS):
     report-scan now lazy-requires expo-mlkit-ocr AND expo-image-picker behind
     try/catch — tile never crashes; photo paths show "not in this version
     yet", PDF + type-instead still work on #32 today. (Publish OTA with
     `--platform ios`; `--platform all` fails in the web export — supabase-js
     hits AsyncStorage in Node.)
   - **Build #33 makes photos work**: app.json now has
     `expo-build-properties` (ios.deploymentTarget **16.0** — app becomes
     iOS 16+ only) + `expo-mlkit-ocr` plugin (`iosEngine: "auto"` = Apple
     Vision engine on iOS; no Google pods; module has a full Vision fallback).
     → **GATE for #33: grep the EAS Xcode log for "Installing ExpoMlkitOcr"**
     before uploading to Transporter; then on-device: photograph a printed
     report end-to-end.
2. **Build #32 smoke list still stands** (after the OTA lands, ~2 launches):
   fresh phone login (test numbers, code 123456) → consent → welcome/tips →
   anchor question (NOT colorectal-assumed) → home greeting → glossary
   round-trip (~1-2s) → T2 escalation card → report-scan via **PDF path** +
   pii_guard fallback (photo OCR waits for #33).
3. **Report-scan backend LIVE + prod-smoked** (`976119e`): identifier-laden
   fixture → 6/6 correct findings, CEA → display_only, apply wrote confirmed
   beliefs; test account restored after. Deferred to v1.1: report-extraction
   eval suite; labs.* namespace.
4. **PENDING USER DECISION — "My terms" further speed** (options given
   2026-07-26): (1) drop per-call get_cancer_slug lookup (~0.25s, free);
   (2) streaming = perceived-instant (~half day, OTA-shippable); (3) Groq
   8b-instant + anti-filler prompt (needs quality audit). Gemini Flash-Lite
   parked (≈tie vs current + needs consent-copy revision naming Google).

## Standing operations
- Weekly `python3 scripts/modeler_report.py --all` AND
  `python3 scripts/safety_report.py` → Dr. Csiki packet.
- All lifecycle + safety flags live in prod; `SAFETY_CLASSIFIER_ENABLED=false`
  is the safety-layer kill switch (floor-only).
- After any deploy touching bundling: check `/api/health` →
  `prompt_files: 10, overlays: 10`.

## Blockers / waiting on people
- **Physician review of `config/safety/sage-safety-rules-v0.9.json` = LAUNCH
  BLOCKER** before real patients (Dr. Csiki proposed; asked in the 2026-07-21
  supervisor email).
- sage-dev seeding needs the prod DB password → steps in
  `supabase_migrations/README.md` (project `eizhshntrquvqwfsseeh`, $10/mo).
- Supervisor open questions (SAGE_TODO): entity branding, mysage.chat DNS,
  pilot recruiting timing. Trademark check runs later (not blocking builds).

## Shipped reference (details live in SAGE_TODO + memory, not here)
- Safety layer LIVE 2026-07-22 (tiers, audit table, eval gate 100%); Flask
  boundary CONFIRMED permanent by supervisor; guidelines adoption done
  (accounts split, AI_CALL telemetry, prompts-as-files, direct supabase-js
  phone OTP — Flask `/api/auth/phone/*` deprecated, DELETE next release).
- Glossary (`glossary_terms` in prod, explain + CRUD endpoints) verified
  end-to-end in prod 2026-07-26.
- Legacy `handle_new_user` trigger fixed 2026-07-25 (unused `user_profiles`
  table 500'd all phone signups — falls back to auth uid now).

## Next follow-up eval windows (one variable each)
1. Voice rules into the system prompt (no em dashes + sixth-grade — Kimi still
   emits em dashes); prompt changes must bump SHA pins.
2. Modernize `scripts/test_all_features.py` literal-substring checks
   (6 known artifacts, SAGE_TODO Workstream C).

## Open follow-ups (unstarted, still valid)
- Learning-loop activation (attorney checklist in docs/compliance/).
- Web SPA parity (chips are mobile-only; web ignores pending_confirmations).
- Retire `chat_messages` double-write + legacy endpoints once old builds age out.
- Delete the dead duplicate Vercel project (`wondrchat-nine.vercel.app`).
- RLS enable+policy migrations for core tables (patient_profiles,
  conversations, messages — currently service-role-guarded only).
- Consent-management UI: verify withdraw/restore end-to-end.
