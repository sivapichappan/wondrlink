# HANDOFF — active work

_Keep this for in-flight work only. Fold anything permanent into `.claude/CLAUDE.md`
and prune the rest. Last updated: 2026-07-26._

## IN FLIGHT RIGHT NOW

1. **eas build #2 is RUNNING** (user started it 2026-07-26). It carries: the
   TestFlight feedback round (no assumed cancer focus, consent checkbox layout,
   Back labels, centered "Tell me how you're feeling, {name}" home, welcome +
   usage-tips onboarding intro), the 21-surface NativeWind Pressable repair
   (incl. CrisisModal 911/988 buttons), New-chat→fresh-Home navigation, the
   branding-constant refactor (store listing = **MySage**, product = Sage),
   the **My terms glossary** page, and the profile-builder plain-language pass
   (no ECOG, biomarkers reframed).
   → When the user reports it done: **commit the `mobile/app.json` buildNumber
   bump** and walk the on-device smoke: fresh phone login (test numbers work,
   e.g. code 123456) → consent (checkboxes inline) → welcome/tips → basics →
   anchor question (NOT colorectal-assumed) → home greeting → glossary
   round-trip → a T2 message shows the escalation card.
2. **Report-scan SHIPPED 2026-07-26** (`976119e` backend + `d640611` mobile).
   Backend LIVE and prod-smoked end-to-end (identifier-laden fixture → 6
   correct findings, CEA → display_only, apply wrote confirmed beliefs; test
   account restored after). Architecture: images never leave the phone
   (on-device OCR via `expo-mlkit-ocr 0.2.7`, alternate `expo-ocr-kit`) →
   `deidentify_report_text` + PII guard → extractor → review-screen
   confirmation → `/api/report/apply` writes confirmed beliefs (pending queue
   bypassed by design). The SCREEN + native modules (expo-image-picker,
   expo-mlkit-ocr, NSCameraUsageDescription) need **eas build #3** — the
   currently running build #2 does NOT include them. Deferred to v1.1:
   report-extraction eval suite; labs.* namespace. USER OPS on build #3:
   photograph a real printed report (OCR quality is manual-only
   verification), PDF path, pii_guard fallback, save round-trip.

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
