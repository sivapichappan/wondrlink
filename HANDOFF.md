# HANDOFF — active work

_In-flight work only. Durable facts live in `.claude/CLAUDE.md` and
`.claude/rules/`; shipped detail lives in SAGE_TODO.md and auto-memory.
Last updated: 2026-08-03._

## RESUME HERE — the reviewer app is LIVE in production; nobody has reviewed anything yet

Reviewers are now ordinary users of the app. A clinician signs up, picks "I am an
oncologist", fills in credentials, and waits; an admin approves from **Reviewer
applications** in the drawer; they then get the whole app with **Approvals** as
one more row in it. Their chat runs on a synthetic patient in separate tables
(§5.5), so no patient_id exists in that path to bind to by mistake.

**Shipped to prod 2026-08-02/03.** Migration applied, backend deployed, mobile on
TestFlight as **v1.2.0 build 37**. 820 tests pass, tsc clean, Pressable scan
clean, working tree clean and pushed.

### THE NEXT ACTION IS A PHYSICIAN WORKING THE QUEUE

**81 candidates, 0 approved, 0 attestations, 0 published versions.** Every part
of the machine has been proven except the part that needs a clinician. The
33-step production probe covers apply → refused-while-pending → approved →
sandbox chat → queue still signs; what it cannot cover is whether the cards read
well to an oncologist over a three-hour sitting.

### Accounts that exist in production

| who | email | role |
|---|---|---|
| owner | `sivapichappan@gmail.com` | admin |
| Naveen Murugan | `naveen@wondrlink.com` | admin |
| Dr. Ildiko Csiki | `ildiko@wondrlink.com` | reviewer_attesting |

Two admins on purpose: an admin cannot decide their own application, so with one
admin nobody could ever re-approve them. **An admin cannot attest and an
attesting physician cannot approve applications** (§5.1) — verified both ways.

**`test.doctor.a@wondrlink.com` and `test.doctor.b@wondrlink.com` are test
accounts still sitting in prod** (both active, both with sandboxes, one push
device registered under Beta). Delete when device testing is finished.

### Known gaps, in the order they will bite

1. **Only CHAT runs on the sandbox.** Care snapshot, check-ins, trends, profile,
   report scan and trials still read and write patient tables, so a reviewer
   tapping any of them gets errors. The owner's direction was "test all
   features"; today it is "test the chat". Chat was done first because it is the
   headline and the one §5.5 specifies. The seam to copy is `lib/sandbox_chat.py`
   plus `_active_reviewer_row()` in `api/index.py`.
2. **22 concepts still have no `display_patient`**, which blocks PUBLISHING even
   after approval. `trastuzumab` is the known hard one: the drafting model keeps
   reaching for "targeted therapy for HER2 positive cancer" and the jargon gate
   keeps refusing it. A clinician should name these.
3. **`publish.tsx` is unreachable** — nothing in the app produces a `versionId`,
   so the last step of the pipeline has no route into it. Phase 5 ends with a
   published version, so this needs solving before then.
4. `concept` has no provenance column, so a physician-proposed name (D3) and a
   pipeline-drafted one are indistinguishable once stored.

### Push notifications — shipped, one step short of confirmed

APNs key uploaded (Key `347234HZT9`, team `F3NVCH942C`), Push capability enabled
on `org.wondrlink.wondrchat`, provisioning profile regenerated, and the binary
gate PASSED on build 37: `ExpoPushTokenManager`, `ExpoNotification`,
`ExpoDevice` all present in the executable and `aps-environment` = **production**
(the value TestFlight needs; development delivers nothing to a tester, silently).

An approval was sent to a real device and **Expo accepted it for delivery
(`delivered: 1`)**. Receipt on the handset has NOT been confirmed by the owner —
that is the one link in the chain still unwitnessed.

`FEATURE_PUSH_NOTIFICATIONS=true` is set in Vercel production.

### What this session fixed that was not in the plan

- **Every sandbox route 500'd on its first real request.** `lib/sandbox_chat.py`
  used the ANON client; the sandbox tables have RLS on with no policies, so the
  SELECT returned 200 with ZERO ROWS rather than failing. The code concluded the
  reviewer had no sandbox and tried to create a second one, and only the INSERT
  said anything. Silent-empty-read is the documented failure mode of a GRANT with
  no policy — and no offline test would have caught it, only the production probe.
- **Reviewers were trapped in the review stack.** Each screen is opened straight
  from the drawer, so it is the first route in that nested stack and
  react-navigation renders no back button; the route beneath is on the PARENT
  stack, which it will not cross. Force-quitting was the only exit.
- **`HeaderBack` called `router.back()` with no `canGoBack()` guard**, shared by
  tools/profile/settings. Harmless until a tapped notification could cold-start
  the app onto a deep route, where `back()` with nothing beneath does nothing and
  the only exit silently dies.
- **`TextField` destructured `onFocus`/`onBlur` out of the props spread and never
  put them back**, so the focus border never lit and every caller's handlers were
  dropped. Regression from the show-password toggle earlier the same day.

## Blockers / waiting on people

- **Physician review of `config/safety/sage-safety-rules-v0.9.json` = LAUNCH
  BLOCKER** before real patients (Dr. Csiki proposed; asked in the 2026-07-21
  supervisor email). Unchanged.
- **Rotate the sage-dev service-role key.** It was pasted in a chat.
  `.env.development` holds it and is gitignored (`.env.*`); rolling it in the
  dashboard is the fix.
- **Email pipeline**: custom SMTP → paste the six templates in
  `config/email_templates/` → turn on "Confirm email". Until then only
  hand-provisioned addresses can sign in, which is why reviewer accounts are
  created by script rather than by registering.
- Supervisor open questions (SAGE_TODO): entity branding, mysage.chat DNS, pilot
  recruiting timing.

## Standing operations

- Weekly `python3 scripts/modeler_report.py --all` AND
  `python3 scripts/safety_report.py` → Dr. Csiki packet.
- `SAFETY_CLASSIFIER_ENABLED=false` is the safety-layer kill switch (floor-only).
- After any deploy touching bundling: check `/api/health` →
  `prompt_files: 12, overlays: 10`.
- After any build adding a native module: download the `.ipa` and `strings` the
  executable for the module class BEFORE Transporter. A FINISHED build proves the
  compiler ran, not that the module linked (build #32 shipped broken that way).

## Open follow-ups (unstarted, still valid)

- Learning-loop activation (attorney checklist in docs/compliance/).
- Web SPA parity (chips are mobile-only; web ignores pending_confirmations).
- Retire `chat_messages` double-write + legacy endpoints once old builds age out.
- Delete the dead duplicate Vercel project (`wondrchat-nine.vercel.app`).
- RLS enable+policy migrations for core tables (patient_profiles, conversations,
  messages — currently service-role-guarded only).
- Consent-management UI: verify withdraw/restore end-to-end.
- The Sentry "Upload Debug Symbols" build phase runs on every build (ambiguous
  dependencies). Costs build minutes, nothing else.

## Next eval windows (one variable each)

1. Voice rules into the system prompt (no em dashes + sixth-grade — Kimi still
   emits em dashes); prompt changes must bump SHA pins.
2. Modernize `scripts/test_all_features.py` literal-substring checks
   (6 known artifacts, SAGE_TODO Workstream C).

## Where the durable facts live (do not re-derive)

- `.claude/rules/connection-map.md` — exact-match citations, re-anchoring, the
  PHI boundary and its import rule, corpus-ingest failures, the reasoning-model
  call config, how to read a zero-candidate run, batching, corroboration.
- `.claude/rules/supabase-migrations.md` — probe as the app's role not as
  postgres; `BEFORE DELETE` triggers must `RETURN COALESCE(NEW, OLD)`; pinned
  search_path; cardinality vs array_length; a GRANT without a policy returns
  zero rows silently.
- `.claude/rules/mobile-ui.md` — the NativeWind Pressable trap, the binary gate,
  Metro's fatal factory throws, the iOS 16 floor, OTA `--platform ios`.
- `PLAN.md` — connection-map plan, decisions D1–D7, the 12 spec-vs-repo
  divergences. `SPEC-connection-map.md` — the spec itself.
- Env for connection-map scripts: `set -a; . ./.env.development; set +a`, then
  take ONLY `TOGETHER_API_KEY` from `.env` — sourcing all of `.env` breaks the
  DB connection.

## Connection-map corpus (reference — do not re-ingest)

29 documents, 896 sections, ingested with BOTH extraction fixes (two-column
gutter detection AND `x_tolerance=1`). 82 edges, 137 citations, every citation an
exact match against source bytes. 28 edges carry more than one citation; 21 are
cited by more than one document. 3 tier-B chains from pass 2, each surfaced with
its `chain_reasoning` and labelled "Proposed reasoning, not a quotation".
