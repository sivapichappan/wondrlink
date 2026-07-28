# HANDOFF — active work

_Keep this for in-flight work only. Fold anything permanent into `.claude/CLAUDE.md`
and prune the rest. Last updated: 2026-07-27._

## IN FLIGHT RIGHT NOW

0. **Connection map Phase 1 (schema/migrations/concept seed/corpus ingest) —
   DONE, gate met 2026-07-28.** Spec at `SPEC-connection-map.md`, plan +
   integration-point map + the 12 spec-vs-repo divergences at `PLAN.md`.
   Commits `8ac9993`..`2bd9caf`. 350 tests green. The five
   `supabase_migrations/2026_07_28_connection_map_*.sql` files are applied to
   **sage-dev only** (`eizhshntrquvqwfsseeh`); **prod is untouched** and stays
   that way until you say otherwise. All 29 probes in
   `docs/connection_map/phase1_probe_checklist.md` pass, re-verified against a
   from-scratch re-apply of the committed files; sage-dev left at zero rows.
   NOT DONE by design: seeder/ingester have not been RUN against sage-dev
   (needs its service key, or seed via MCP); no extraction, no runtime, no
   patient-facing surface exists yet.

0b. **Connection map Phase 2 (reviewer roles + PHI boundary + audit log) —
   built and probed 2026-07-28** (`a9b0aed`, 389 tests green). Owner chose the
   **restricted database account** over app-layer separation. §5.8's dedicated
   Postgres pool is unbuildable here (no driver, no connection string), so the
   boundary is a `sage_review` Postgres role selected by a JWT `role` claim,
   which PostgREST honours natively. **Proved on sage-dev:** as `sage_review`,
   `patient_edge`/`patient_edge_event` give *permission denied for table* and
   `auth` gives *permission denied for schema*. Probes:
   `docs/connection_map/phase2_probe_checklist.md`.
   Adversarial review then found and fixed three holes (`22c0050`): the
   import-graph gate omitted `supabase_client` (the service-role client) so a
   review module importing it passed CI; reviewer activation was broken 100% of
   the time by a PL/pgSQL guard that parse-analysis defeats, and granting the
   review role write access there would have made the trigger a
   patient-existence oracle; and `reviewer_assignment` accepted an empty
   `tiers` array (`array_length` of an empty array is NULL and CHECKs pass on
   NULL). All re-probed. 395 tests green.
   TWO THINGS STILL OPEN on Phase 2: (a) the PATIENT-side half of acceptance #5
   is unproven — that trigger needs `patient_profiles`, absent on unseeded
   sage-dev, so re-run the reviewers migration after bring-up or verify on prod
   at release (the reviewer-side half is now fixed and proven); (b) acceptance
   #2 (every `/review/*` route uses the restricted client) has no routes yet —
   it lands with the Phase 3 workspace and must not be forgotten.

0c. **Connection map Phase 3, database half — DONE and proven 2026-07-28**
   (`3ed75c1`, 439 tests green). Attestation records + the §5.7 publication
   gate. An edge went candidate → approved → physician-signed → published with
   a frozen hash on sage-dev; 12 probes in
   `docs/connection_map/phase3_probe_checklist.md` cover acceptance #6-#10,
   #25 and §4.5. Key design: signing snapshots the reviewer's status so
   revoking someone later does not invalidate what they signed while active;
   "editing voids the attestation" is a content hash over the edge plus every
   evidence row; the gate re-verifies every citation against its source AT
   publication and reports all blockers at once; there is no override.
   REMAINING IN PHASE 3: `/api/review/*` endpoints on the restricted client
   (this is where acceptance #2 gets proven), the D1 loose re-check of
   physician edits, and the review workspace itself. **Frontend decision
   REVERSED by the owner 2026-07-28: the workspace is a MOBILE surface.**
   "Everything needs to put the phone app first, that is the main goal/product"
   — and internal clinician tools are not an exemption. §5.4's desktop
   side-by-side + keyboard-shortcut layout gets adapted to stacked panels with
   a triage-style flow (see `.claude/CLAUDE.md` conventions and the
   mobile-is-the-product memory). The PHI boundary is unaffected: the app talks
   to Flask, and `/api/review/*` uses the restricted `sage_review` client
   regardless of what renders it. New mobile need this creates: reviewer-role
   gating in the app, which has none today (`RootGate` gates on server booleans
   only) — the same gating Phase 10's sandbox will need.
   Owner decisions D1-D4 (incl. tier C redefined and now allowed to reach
   patients once attested) are recorded in PLAN.md; D2 will deliberately flip
   two Phase 1 guardrail tests when implemented. Tier C also needs an
   attestation-wording variant with attorney sign-off before it ships.

1. **Name-mismatch warning — one user-ops check left.** Shipped 2026-07-27
   (`a038899` backend + `fb759ad` mobile, OTA `f51b42cd`; prod-smoked:
   mismatch→true, match→false, zero name echo; invariants locked in
   `.claude/rules/backend-python.md`). REMAINING: user relaunches the app
   twice (OTA pickup), rescans `~/Downloads/
   SAMPLE-pathology-report-for-app-testing.pdf` (fictional "Jane Q. Sampleton"
   ≠ account name) → amber banner should sit above the review findings.
   Watch the `report_scanned` event's `name_mismatch` boolean over time for
   the false-positive base rate before considering stricter matching.
2. **PENDING USER DECISION — "My terms" further speed** (options given
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
  `prompt_files: 12, overlays: 10`.

## Blockers / waiting on people
- **Physician review of `config/safety/sage-safety-rules-v0.9.json` = LAUNCH
  BLOCKER** before real patients (Dr. Csiki proposed; asked in the 2026-07-21
  supervisor email).
- sage-dev seeding needs the prod DB password → steps in
  `supabase_migrations/README.md` (project `eizhshntrquvqwfsseeh`, $10/mo).
- Supervisor open questions (SAGE_TODO): entity branding, mysage.chat DNS,
  pilot recruiting timing. Trademark check runs later (not blocking builds).

## Shipped reference (details live in SAGE_TODO + memory, not here)
- **Build #34 installed + device-verified 2026-07-27**: report-scan photo OCR
  end-to-end (9/9 findings, labs display-only, de-id held). The #32 crash
  saga is CLOSED — every lesson (autolinking silent skip, Metro fatal on
  factory throws, binary strings gate, iOS 16 floor, Apple Vision engine,
  OTA `--platform ios`) lives in `.claude/rules/mobile-ui.md` + CLAUDE.md.
  Builds #32/#33 superseded; buildNumber 34 committed (`d02c601`).
- Safety layer LIVE 2026-07-22 (tiers, audit table, eval gate 100%); Flask
  boundary CONFIRMED permanent by supervisor; guidelines adoption done
  (accounts split, AI_CALL telemetry, prompts-as-files, direct supabase-js
  phone OTP — Flask `/api/auth/phone/*` deprecated, DELETE next release).
- Glossary (`glossary_terms` in prod, explain + CRUD endpoints) verified
  end-to-end in prod 2026-07-26.
- Report-scan backend deferred-to-v1.1 items: report-extraction eval suite;
  labs.* namespace.
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
