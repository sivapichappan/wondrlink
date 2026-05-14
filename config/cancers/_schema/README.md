# config/cancers/

Per-cancer configuration. Each cancer is a slug-named directory.

## Files per cancer

| File | Required when `ready: true` | Purpose |
|---|---|---|
| `cancer.yaml` | yes | Metadata: slug, display_name, staging system, biomarker panel, common regimens, ClinicalTrials.gov conditions, `ready` flag |
| `overlay.md` | yes | Hand-written per-cancer prompt insert (the ~15% that varies). Composed with the base prompt by `lib/prompts/overlay.py`. |
| `clinical.schema.json` | yes | JSON Schema validating the per-cancer `clinical` payload in `patient_profiles.clinical` |
| `phase_rubric.yaml` | yes | Phase classification thresholds + per-phase suggested questions + describe_phase descriptors |
| `surveillance.yaml` | yes (clinician-signed) | Deterministic surveillance milestones for that cancer |
| `trial_synonyms.yaml` | optional (falls back to `cancer.yaml.clinicaltrials_conditions`) | Extra condition synonyms + stage-specific terms for ClinicalTrials.gov queries |
| `resources.yaml` | yes | Per-cancer advocacy orgs and helplines |
| `biomarker_implications.yaml` | yes | Biomarker → drug-class mappings for trial scoring and prompt overlay |

## `ready` flag

`cancer.yaml.ready` is `true` only when **all** of:
- All files above are filled and validate against their schemas
- Surveillance rubric is clinician-signed
- Per-cancer eval set passes the gate
- Corpus-completeness checklist passes

When `ready: false`, the system:
- Accepts the slug at signup
- Falls back to `general`-tagged RAG corpus only
- Returns a "surveillance schedule for {display_name} is coming soon — discuss with your oncologist" message instead of generating
- Scores clinical trials on age/sex/distance/treatment-line only (no biomarker bonuses)
- Uses a stub overlay prompt that says "general cancer support"

## Validators

- `lib/prompts/overlay.py` — loads `cancer.yaml` + `overlay.md`, validates against `_schema/cancer.schema.json`
- `lib/profile_validator.py` — validates `patient_profiles.clinical` against `<slug>/clinical.schema.json`
- `scripts/eval/run_evals.py --cancer <slug>` — runs the per-cancer eval suite

## Adding a new cancer

1. Create `config/cancers/<slug>/` with all files above
2. Add the slug to the canonical list in `lib/cancer_registry.py` (auto-discovered at import)
3. Tag corpus chunks with the new slug (`scripts/backfill_chunk_metadata.py` updates the curated `data/_filename_to_metadata.yaml` map)
4. Author golden + off-topic + cross-cutting + safety eval suites in `scripts/eval/suites/<slug>/`
5. Pass the gate (clinician sign-off, eval thresholds), flip `ready: true`
