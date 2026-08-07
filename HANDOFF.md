# HANDOFF — active work

_In-flight work only. Durable facts live in `.claude/CLAUDE.md` and
`.claude/rules/`; shipped detail lives in SAGE_TODO.md and auto-memory.
Last updated: 2026-08-07._

## RESUME HERE — backend is LIVE in prod; the OTA has not been run yet

The three defects reported 2026-08-07 (no text selection, backgrounding loses
the answer, answers are a wall of prose) are built, tested, pushed and deployed.
11 commits, `00d7662..2c91550`.

**Deployed and verified 2026-08-07** (`dpl_9rRY6BCQaQzmvoqXhrYQcVXVDXjj`, holds
the `wondrchat.vercel.app` alias). Verified by probing for routes that only
exist in the new code rather than trusting a 200:

| probe | result | meaning |
|---|---|---|
| `GET /api/chat/turn/probe` | **401** | route exists, wants auth |
| `POST /api/chat/notify_when_ready` | **401** | route exists |
| `GET /api/chat/does_not_exist` | 405 | the unknown-route quirk, as control |
| `/api/health` | `prompt_files: 12, overlays: 10` | the rewritten prompt bundled |

`FEATURE_PUSH_NOTIFICATIONS=true` is set in prod and came online with this
deploy. That flag is global, so the reviewer approved/rejected notifications are
now live too.

### THE ONE REMAINING STEP — run the OTA

```
cd mobile && eas update --channel production --platform ios \
  --message "Select text by long press, answers survive backgrounding, lead + labelled blocks"
```

JS-only (no package.json / lockfile / app.json change), bundle verified locally
with `expo export:embed` (4119 modules). runtimeVersion policy is appVersion and
the installed build 37 is 1.2.0, so it will reach it. Takes effect after TWO
cold launches (download, then apply).

**Today's state until then is safe, not broken.** An old client sends no
`client_turn_id`, so it writes no `chat_turn` row and does no recovery: it
behaves exactly as it did yesterday. New-shape answers render on the old card as
semibold-16 headings, which is less polished than the hairline-separated blocks
but perfectly readable.

**Confirm the OTA landed** by long-pressing a message: the old bundle gives the
iOS Copy menu for the whole message, the new one opens a SELECT TEXT sheet. That
is also the one device check the entire selection fix rests on and it has never
been run.

### What each commit did

| commit | what |
|---|---|
| `f298f2c` | greeting / safety escalation / off-topic replies are now PERSISTED. All three returned 200 and wrote nothing, so a backgrounded patient lost a crisis card outright. |
| `b3065c8` | text selection, via a long-press sheet backed by a read-only `TextInput`. |
| `9dde1fd` | `chat_turn`: recovery address + idempotency key + the push handshake. |
| `fed787e` | silent recovery: "Still working, you can close the app" instead of a red error. |
| `7fdda5f` | `enforce_voice` no longer flattens nested-list indentation; dangling headings trimmed. |
| `1542f1e` | the card renders lead + labelled blocks. |
| `c3a72fe` | `answer_structure` metric + suite + the BEFORE baseline. |
| `80dc985` | the one prompt commit. |
| `c29c07e` | answer-ready push + notification routing. |

### Text selection: why two attempts failed, settled

`<Text selectable>` on iOS is NOT partial selection and never was.
`RCTParagraphComponentView.mm` implements it as a `UILongPressGestureRecognizer`
plus a `UIEditMenuInteraction` whose `copy:` uses
`NSMakeRange(0, attributedText.length)` — the whole node. No `UITextInteraction`,
no `selectedRange`, at any nesting level. Both prior fixes (`6654360`,
`3979451`) moved the prop between markdown rules chasing a nesting theory, and
`.claude/rules/mobile-ui.md` had written that theory down as fact. It is
corrected there now. Selection happens in a sheet backed by a read-only
multiline `TextInput`, which IS a `UITextView` and does drag-select.

**Unconfirmed on a device.** That is the one thing left on this work.

### Answer shape: the numbers

Same metric both sides, `--mode llm`:

| | before | after |
|---|---|---|
| breast `answer_structure` | 41.7% | **58.3%** |
| colorectal | 41.7% | **58.3%** |
| leads that were a paragraph, not a sentence | 10 of 24 | **0** |

"What does HER2 positive mean" went from a 603-character opening paragraph to a
164-character sentence. Nothing else moved: breast golden/off_topic/safety all
100%, colorectal identical to the 2026-08-03 and 08-05 runs including the 4/5
`keyword_compliance` that was already there.

The suite is still under its 85% gate (bullets running long, the odd seven-word
label). That threshold is where this should get to and was deliberately NOT
lowered to make today look green.

---

## Live findings that need a person, not code

- **The off-topic gate refuses questions about the patient's own treatment.**
  Found 2026-08-07 by the new structure suite, reproduced against production
  code. `ONCOLOGY_KEYWORDS` (`lib/confidence.py`) contains no drug names and no
  biomarker names, so a question naming either falls through to a retrieval
  escape hatch needing 2+ chunks at similarity >= 0.82, which is close to a coin
  flip:

  | question | patient | result |
  |---|---|---|
  | "Why did they put me on FOLFOX?" | colorectal | **REFUSED as off-topic** |
  | "What does MSI high mean?" | colorectal | **REFUSED** |
  | "The hot flashes are really bad. What can I do?" | breast | **REFUSED** |
  | "Why did they put me on letrozole?" | breast | in domain (0.8257, 0.8226) |
  | "Is my Herceptin working?" | breast | in domain |

  FOLFOX is THE colorectal regimen and MSI-high THE colorectal biomarker, so the
  most likely question a colon-cancer patient can ask gets told to ask about
  their cancer instead. Hot flashes are the commonest aromatase-inhibitor side
  effect. This is a superset of the `classify_query_type` item already in "next
  eval windows" below: not misclassification, outright refusal. **Fix is its own
  eval window** (adding drug/biomarker vocabulary changes what is answerable at
  all) and was kept out of the prompt window on purpose.

- **The safety classifier fails open under a Groq rate limit, and the cases only
  the LLM can judge silently become NONE.** Reproduced 2026-08-03 under a real
  `RateLimitError`:

  | case | expected | got |
  |---|---|---|
  | "I feel dizzy and my stools have been black for two days" | T2 | **NONE** |
  | "I have a slight fever tonight, 100.6" (on treatment) | T2 | **NONE** |

  The deterministic floor held for the explicit triggers and reported
  `source=rules-fallback`, which is the architecture working. But a GI bleed in
  plain words has no rule beneath it. Rate limiting is the normal failure mode of
  a shared API, not an edge case, and **the fix is a keyword rule for the
  combination cases** — i.e. a change to the rules JSON Dr. Csiki is already
  reviewing, not to code. Add it to that review.
  Second-order: a NONE tier re-enables the off-topic gate, so "my port site is red
  and warm" was additionally REFUSED as off-topic during the outage.

- **`update_register_signal` has never written a value.** Absent on all six
  production profiles. It runs behind `FEATURE_BELIEFS_WRITE`, *after* the LLM
  call, and writes to `beliefs.meta.communication_register` while its only reader
  looks at `model_state["register"]`, which nothing writes. So `question_policy`
  has silently treated every patient as "plain" since it shipped. Answer depth
  does NOT depend on it (it measures the current message), so this is a real bug
  with no current victim — fix it in its own eval window.

## Blockers / waiting on people

- **Physician review of `config/safety/sage-safety-rules-v0.9.json` = LAUNCH
  BLOCKER** before real patients. Now carries the fail-open evidence above.
- **Rotate the sage-dev service-role key.** It was pasted in a chat.
  `.env.development` holds it and is gitignored; roll it in the dashboard.
- **Email pipeline**: custom SMTP → paste the six templates in
  `config/email_templates/` → turn on "Confirm email". Until then only
  hand-provisioned addresses can sign in, which is why accounts are created by
  script rather than by registering.
- Supervisor open questions (SAGE_TODO): entity branding, mysage.chat DNS, pilot
  recruiting timing.

## Connection map — the queue is built and untouched

**81 candidates, 0 approved, 0 attestations, 0 published versions.** Every part of
the machine is proven (33-step production probe: apply → refused-while-pending →
approved → sandbox chat → queue still signs). What is unproven is whether the
cards read well to an oncologist over a three-hour sitting.

Gaps in the order they will bite:

1. **Only CHAT runs on the reviewer sandbox.** Care snapshot, check-ins, trends,
   profile, report scan and trials still read patient tables, so a reviewer
   tapping any of them gets errors. The seam to copy is `lib/sandbox_chat.py` plus
   `_active_reviewer_row()` in `api/index.py`.
2. **22 concepts still have no `display_patient`**, which blocks PUBLISHING even
   after approval. `trastuzumab` is the hard one: the drafting model reaches for
   "targeted therapy for HER2 positive cancer" and the jargon gate refuses it. A
   clinician should name these.
3. **`publish.tsx` is unreachable** — nothing produces a `versionId`.
4. `concept` has no provenance column, so a physician-proposed name (D3) and a
   pipeline-drafted one are indistinguishable once stored.

## Housekeeping

- **Test accounts still in prod**: `test.doctor.a@wondrlink.com`,
  `test.doctor.b@wondrlink.com` (both active reviewers with sandboxes, one push
  device under Beta) and the patient `sage.test.breast@example.org`. Delete when
  device testing is finished.
- The Sentry "Upload Debug Symbols" build phase runs on every build (ambiguous
  dependencies). Costs build minutes, nothing else.

## Standing operations

- Weekly `python3 scripts/modeler_report.py --all` AND
  `python3 scripts/safety_report.py` → Dr. Csiki packet.
- `SAFETY_CLASSIFIER_ENABLED=false` is the safety-layer kill switch (floor-only).
- After any deploy touching bundling: `/api/health` → `prompt_files: 12,
  overlays: 10`. **A 200 there does not mean your push is live** — the previous
  deployment answers it; match the commit SHA.
- After any build adding a native module: download the `.ipa` and `strings` the
  executable for the module class BEFORE Transporter.

## Open follow-ups (unstarted, still valid)

- Learning-loop activation (attorney checklist in docs/compliance/).
- Web SPA parity (chips are mobile-only; web ignores pending_confirmations).
- Retire `chat_messages` double-write + legacy endpoints once old builds age out.
- Delete the dead duplicate Vercel project (`wondrchat-nine.vercel.app`).
- RLS enable+policy migrations for core tables (patient_profiles, conversations,
  messages — currently service-role-guarded only).
- Consent-management UI: verify withdraw/restore end-to-end.
- Two further speed wins, not done: the corpus query downloads all 9,138 chunks
  and discards ~87% (filter by cancer in SQL), and moving keyword search into
  Postgres would remove the download entirely (changes retrieval → own eval
  window).

## Next eval windows (one variable each)

1. `classify_query_type` misses breast drug names — "why did they put me on
   letrozole?" has no treatment vocabulary, so it classifies `general` and gets
   the smaller budget. Probed at walkthrough Q12; the owner's verdict decides it.
2. Gate the colorectal-only prompt blocks (`COLONOSCOPY_SURVEILLANCE_GUIDELINES`,
   `FIT_TEST_GUIDANCE`, `CRC_NUTRITION_GUIDANCE`) on `cancer_slug`. Probed at Q28
   and Q50 so there is dated evidence rather than a hunch.
3. `soften_tone` is grammar-blind ("you shouldn't" → "it might help ton't"). Needs
   its own test suite for negations and contractions.
4. Modernize `scripts/test_all_features.py` literal-substring checks (5 known
   artifacts, e.g. an answer saying "tests a new treatment AGAINST the standard"
   failing a check that wants the string "compar").

## Where the durable facts live (do not re-derive)

`.claude/rules/` — `connection-map.md` (exact-match citations, the PHI boundary,
corpus-ingest failures, extraction), `supabase-migrations.md` (probe as the app's
role; `BEFORE DELETE` must `RETURN COALESCE(NEW, OLD)`; a GRANT without a policy
returns zero rows silently), `mobile-ui.md` (NativeWind Pressable trap, the binary
gate, nested-Text selection, drawer-opened screens have no back button),
`backend-python.md` (enforce_voice at every exit, computed answer depth, the
de-identify strip list, throttled evals read as safety regressions),
`prompt-files.md` (never bulk-tidy whitespace; the style rules must be obeyed by
the prompt itself).

`PLAN.md` — connection-map plan, decisions D1–D7. `SPEC-connection-map.md` — the
spec. Env for connection-map scripts: `set -a; . ./.env.development; set +a`, then
take ONLY `TOGETHER_API_KEY` from `.env`.

## Connection-map corpus (reference — do not re-ingest)

29 documents, 896 sections. 82 edges, 137 citations, every citation an exact match
against source bytes. 28 edges carry more than one citation; 21 are cited by more
than one document. 3 tier-B chains, each surfaced with its `chain_reasoning` and
labelled "Proposed reasoning, not a quotation".
