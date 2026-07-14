# The Modeler — connections layer runbook

The per-patient reasoning layer (lifecycle Push 2): a background DeepSeek-V4-Pro pass
(`get_model("modeler")`) over one patient's longitudinal record that maintains
`raw_profile.connections` — the graph the future trial-matching push consumes.

## What one run does

```
trigger (client end-of-conversation / nightly cron / manual)
  └─ debounce: ≥3 new patient_events since watermark, ≥1h since last run, ≤2 runs/day
      └─ assemble input (ALL timestamps as day offsets "T-12d" — guard-safe):
           patient summary (de-identified) + belief digest
           timeline E1..En (60-day tail, shadow_extraction excluded)
           screening series · de-identified conversation excerpts C1..Cn
           guideline excerpts G1..Gn (hybrid_search; PII-scan exempt, public corpus)
           current graph render
      └─ detect_pii_leaks on patient-derived sections → ANY hit aborts the run
      └─ V4-Pro (JSON mode, temp 0.2, max_tokens 2500, 45s timeout, NO Groq fallback)
      └─ strict item-wise validation (see rules below) → merge → calibrate → save
```

Failed runs never advance the event watermark; the merge is identity-keyed, so
duplicate/missed cron deliveries are harmless.

## The graph document (`raw_profile.connections`)

| section | contents | caps |
|---|---|---|
| `edges` | typed links `src --rel--> dst` with `status` hypothesis/corroborated/refuted, `strength`, evidence refs | 50 (prune: refuted → weakest → stalest) |
| `expectations` | internal predictions with absolute windows + machine-checkable `check` specs + optional register-matched `ask` | 10 open / 30 resolved kept |
| `reflections` | synthesized facts, optionally proposing a belief `{path, value}` | 20 |
| `calibration` | hits / misses / expired / hit_rate (+ per-basis) — **the flip-gate metric** | history 20 runs |
| `meta` | watermark, last_run_at/status, daily run counter, model | |

New `patient_events` kinds: `modeler_run`, `expectation_hit|miss|expired`.
Delete-parity is automatic (profile + events are already purged by `delete_all_user_data`).

## Validation rules (enforced in `parse_modeler_output`, not just the prompt)

- Every edge/expectation/resolution/reflection must cite ≥1 evidence ref that
  resolves to the input index (E*/C*/G* or an exact belief path).
- Timing/cycle expectations require treatment-timeline evidence (an event or a
  `treatments.*` belief) — never inferred from symptoms alone.
- Prognosis/survival/mortality vocabulary is rejected anywhere.
- The model may propose `hypothesis` or `refuted` (refuted needs event evidence);
  `corroborated` is **computed**: `times_seen ≥ 2` AND evidence spans ≥2 kinds.
- Per-run caps: ≤8 edges, ≤4 expectations, ≤3 reflections. Violating items are
  dropped individually (`rejects` counted in the `modeler_run` event).

## Reflections → pending queue

When `FEATURE_MODELER_ACTIVE` is on, reflections with a `proposed_belief` are
FORCE-pended through `patient_model.apply_decisions` (never self-commit,
regardless of stakes) — they surface as the same "is that right?" chips and
respect the queue cap of 3 (excess stays `proposed` and retries next run).
In shadow they stay in the JSON for the review report.

## Flags & endpoints

| | |
|---|---|
| `FEATURE_MODELER` | compute + store + report + `GET /api/modeler/graph` (shadow posture) |
| `FEATURE_MODELER_ACTIVE` | consumers live: prompt block, expectation questions, reflection chips |
| `POST /api/modeler/run` | client end-of-conversation trigger (auth; debounce is the real gate) |
| `GET /api/modeler/cron` | nightly catch-up; `Authorization: Bearer $CRON_SECRET` (Vercel sends it); 40s time guard; counts-only response |
| `GET /api/modeler/graph` | caller's own graph JSON |

Both flags are read directly from env with default **false** — never via
`feature_enabled()`. Cron schedule: `0 7 * * *` UTC in `vercel.json` (Hobby =
daily only; a more frequent expression FAILS the deployment).

## Review & the flip

- `python3 scripts/modeler_report.py --all` — per-patient markdown (edges,
  Mermaid sketch, expectations, calibration, reflections, auto-filled flip
  checklist) for supervisor review. Self-scans with the PII guard (date
  patterns exempt — system dates; identity paths never enter the digest).
- `scripts/modeler_viz.html` — local force-directed graph (drag-drop the
  `--json` export, or JWT + fetch). Never deployed.
- Evals: `run_evals.py --cancer colorectal --suite modeler --mode dry` (golden
  fixture, free, part of the standard battery) · `--mode llm` (ONE real V4-Pro
  run, ~$0.05 — deploy checkpoints and pre-flip only).

**Flip checklist (gates `FEATURE_MODELER_ACTIVE`)** — auto-filled in the report:
≥2-week shadow bake across ≥3 active patients · zero `pii_guard` aborts ·
parse-reject rate <10% · **≥10 resolved expectations AND hit-rate ≥0.6** ·
guideline-basis hit-rate ≥ observed-pattern · Dr. Csiki sign-off · dry battery
green. Rollback = unset the flag (consumers vanish next request; shadow keeps
accruing).

## First live smoke (2026-07-14)

One real V4-Pro run against the fixture patient: 7 ops accepted, 1 reflection
rejected by the validator (working as designed). Sample: `FOLFOX --causes-->
neuropathy (0.9)`, `KRAS G12D --contraindicates--> anti-EGFR (1.0)`, plus two
machine-checkable expectations with sane windows. `modeler_integrity` 4/4.
