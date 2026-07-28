# Connection Map — Implementation Specification

**Product:** Sage (WondrLink Foundation)
**Feature:** per-patient relationship map with physician-approved literature seeding
**Pilot cancer:** breast cancer (v1 ships breast only)
**Patient cohort at build time:** zero. v1 is build-and-verify, not a measurement study.
**Version:** 3 — supersedes v2
**Intended reader:** Claude Code, plus human reviewers of this spec

---

## 0. Read this first

This document is the complete scope. If something is not in here, it is out of scope for v1.

Four rules override everything else:

1. **No connection reaches a patient without a physician attestation.** When no attested connection is available, the app falls back to current behavior (§0.1). There is no unattested path.
2. **No cross-patient aggregation except the two count-only controls explicitly permitted in §6.4 and §13.2.** The learning loop remains dormant. Do not read from it, write to it, or make turning it on easier.
3. **Never assert causation to a patient.** Direction is stored and dropped at render. Enforced by test.
4. **Never deceive a patient to obtain a measurement.** No planted false connections. The honesty commitment in §9 runs both ways.

Assumed stack: PostgreSQL, Python backend, React frontend. If the repo diverges, follow the repo.

### 0.1 Fallback behavior

The connection map is **additive**. Every failure mode degrades to the existing RAG chat, silently.

| Condition | Behavior |
|---|---|
| No published map for the patient's cancer | Current RAG chat. No error, no placeholder. |
| Published map, but no instantiated edges for this patient | Current RAG chat. |
| Instantiated edges, none selected this turn | Current RAG chat. |
| Connection-map service unavailable or erroring | Current RAG chat. Log, alert, do not surface. |
| Feature flag off | Current RAG chat. |

A patient must never see a degraded experience, an empty state, or an error attributable to this feature. Test: with the feature fully disabled, chat behavior is byte-identical to the pre-feature baseline.

### 0.2 Changes from v2

| Change | Reason |
|---|---|
| §0.1 explicit RAG fallback | Graceful degradation was implied, not specified |
| Separate reviewer deployment replaced by in-app reviewer role (§5.8) | Reviewers also need a test chat; two apps made that awkward and doubled the work |
| Pass 3: patient-observation candidates (§6.4) | Patient signal may point at a relationship the corpus already supports |
| No em dashes in patient-facing text (§8) | Style requirement |
| §10 expanded to a full breast extraction target set | Was a thin starter list |

---

## 1. Context — what already exists

Do not rebuild any of this.

| System | What it does | How this feature touches it |
|---|---|---|
| **Belief store** | Per-patient facts as `{value, confidence, status: confirmed \| provisional, source, history}` | Read-only. Decides whether a patient "has" a concept. |
| **Modeler** | Scheduled LLM pass emitting structured observations | Two new tasks: score instantiated edges, emit observation candidates. |
| **Question policy** | Coverage scoring picks one gentle question per eligible turn | New question type registered. Arbitration unchanged. |
| **Safety classifier** | Crisis tiers as physician-reviewable JSON | Urgent-flagged edges route here, not to the question policy. |
| **RAG chat** | Retrieval over per-cancer guideline corpora | Confirmed edges injected as context. Also the fallback for everything. |
| **Trial matching** | ClinicalTrials.gov relevance scoring | Confirmed edges as optional features. |
| **Onboarding** | Account creation and consent | Gains the honesty commitment (§9). |
| **Learning loop** | De-identified cross-patient pattern emitter | **DORMANT. Do not touch.** |

---

## 2. What we are building

1. A **master map** for breast cancer: typed concepts and typed relationships with verbatim evidence, each approved by a physician, published as versioned config.
2. **In-app reviewer access**: a role that unlocks a review workspace and a sandbox test chat inside the existing application. No second deployment.
3. An **instantiation and confirmation loop**: master relationships copy onto a patient's map only when both endpoints are already confirmed facts, then surface one at a time through the gentle-question channel.
4. A **patient honesty commitment** at onboarding, plus a path to revise any answer.
5. **Consumers**: confirmed relationships feed chat context, check-in selection, trial ranking.

---

## 3. Non-goals and hard prohibitions

- No neural network trained on patient data. Knowledge graph plus Bayesian counting. No embeddings, GNNs, or learned link prediction.
- No relationship types created at runtime. Closed enum.
- No relationship proposed that is absent from a published master map version.
- No confidence value rendered to a patient in any form.
- No planted, false, or control connections shown to patients.
- No PHI in the review workspace, the reviewer's session, or the sandbox chat.
- No PHI leaves the de-identification boundary for LLM calls.
- No multi-tenancy, org hierarchies, or billing.

---

## 4. Domain model

### 4.1 Concepts

```
concept
  id, slug unique, domain enum, display_clinical, display_patient,
  terminology_system, terminology_code, instrument enum,
  cancer_scopes text[], created_at, updated_at
```

`domain`: `biomarker`, `treatment`, `procedure`, `symptom`, `lab_or_measure`, `daily_life`.
`instrument`: `lab`, `ehr_field`, `report_scan`, `pro_instrument`, `self_report_chat`.

`instrument` is not decorative. A concept measured by a validated instrument and one measured by a patient typing "pretty tired lately" carry different weight downstream.

`display_patient` is mandatory for publication.

### 4.2 Source corpus

```
source_document
  id, title, publisher, edition,
  scope enum        -- 'cancer_specific' | 'general_survivorship'
  cancer text null, file_path, ingested_at
```

Symptom-cluster relationships live mostly in general survivorship sources. A breast-only corpus will underproduce candidates. Ingest both.

### 4.3 Relationship types

| Type | Direction | Patient-facing | v1 enabled |
|---|---|---|---|
| `side_effect_of` | symptom → treatment | yes | **yes** |
| `co_occurs_with` | symmetric | yes | **yes** |
| `indicated_by` | biomarker → treatment | yes | no |
| `monitored_with` | treatment → lab_or_measure | yes | no |
| `mitigated_by` | symptom → daily_life | yes | no |
| `acts_through` | mediation chain | **never** | no |

`acts_through` is authoring-only. A patient cannot validate a mediator.

### 4.4 Master edges and evidence

```
master_edge
  id, src_concept_id, dst_concept_id, relationship enum,
  urgency enum,                      -- 'routine' | 'urgent'
  tier enum,                         -- 'A' | 'B' | 'C'
  status enum,                       -- 'candidate'|'in_review'|'approved'|'rejected'
  candidate_origin enum,             -- 'literature_scan' | 'patient_observation'
  extraction_run_id, extraction_pass int,
  prior_alpha int default 2, prior_beta int default 1,
  expected_prevalence_low numeric null,
  expected_prevalence_high numeric null,
  patient_phrasing text,
  rejection_reason enum null,
  created_at, updated_at,
  unique (src_concept_id, dst_concept_id, relationship)

master_edge_evidence
  id, master_edge_id, source_document_id, section_ref,
  quoted_sentence text NOT NULL, char_offset int, ordinal int
```

**Every evidence row must match its own section character for character**, verified at insert. An edge with zero evidence rows cannot exist.

Tier A carries one evidence row. Tier B carries two or more. Per-quotation strictness is identical.

Tiers, assigned at extraction:

- **A** — stated outright in one sentence of one source.
- **B** — chains two or more verified quotations.
- **C** — no verifiable quotation. **Discarded, never queued.**

### 4.5 Master map versions

```
master_map_version
  id, cancer, version int, status enum,
  published_at, published_by, edge_ids uuid[],
  frozen_hash, governance_note text
```

Published versions are immutable.

### 4.6 Patient edges

```
patient_edge
  id, patient_id, master_edge_id, map_version_id,
  status enum,   -- 'instantiated'|'proposed'|'confirmed'|'refuted'|'retired'
  alpha int, beta int, last_asked_at, ask_count int default 0,
  created_at, updated_at,
  unique (patient_id, master_edge_id)

patient_edge_event      -- append-only
  id, patient_edge_id, event_type, from_status, to_status,
  question_instance_id, actor, payload jsonb, created_at
```

### 4.7 State machine

```
        instantiate            select_for_question
candidate ──▶ instantiated ───────────▶ proposed
                   ▲                     │
                   │                patient answers
                   │                  ┌──┴──┐
                   │               yes│     │no
                   │                  ▼     ▼
                   │             confirmed refuted
                   │                  │     │
                   │                  └──┬──┘
                   │      patient revises │  (§9.3)
                   └──────────────────────┘
                                      │
                                      ▼
                                   retired
```

`refuted → confirmed` and `confirmed → refuted` occur **only** via patient-initiated revision, never via the question policy.

### 4.8 Confidence

Beta posterior. Integers only. Confirmation increments `alpha`, refutation increments `beta`, revision decrements one and increments the other. Point estimate available internally, **never rendered**. Updates idempotent per `question_instance_id`.

---

## 5. Physician approval and access control

Build this first.

### 5.1 Roles

```
reviewer
  id, email citext unique, full_name,
  credential enum,      -- 'MD'|'DO'|'NP'|'PA'|'PharmD'|'RN'|'other'
  npi, license_state, specialty, institution,
  affiliation enum,     -- 'internal' | 'external'
  role enum, status enum,
  invited_by, activated_at, created_at, updated_at
```

| Role | Can review | Can attest | Can publish | Can manage reviewers |
|---|---|---|---|---|
| `observer` | read-only | no | no | no |
| `reviewer_clinical` | Tier A, B | no | no | no |
| `reviewer_attesting` | Tier A, B | **yes** | no | no |
| `admin` | read-only | no | yes | yes |

`reviewer_attesting` requires `credential ∈ {MD, DO}` — database check constraint.

An `admin` cannot attest. The person cutting the release is not the person vouching for the content.

**A reviewer account and a patient account are mutually exclusive.** Enforce at the database level. If a clinician is also a patient, they need a second account.

### 5.2 Granting access

1. Admin creates the reviewer record. Status `invited`.
2. Single-use, 72-hour activation link by email.
3. Reviewer sets up auth (magic link plus optional TOTP), confirms credentials, accepts attestation terms. Status `active`.
4. All steps written to `audit_log`.

No self-registration. No public signup.

### 5.3 Scoping

```
reviewer_assignment
  id, reviewer_id, cancer, tiers text[], granted_by, granted_at, revoked_at
```

Enforce with a Postgres row-level policy, not only in the API layer. For v1 every assignment is `cancer = 'breast'`.

### 5.4 Review workspace

Lives in the main application at `/review`, gated on reviewer role. One candidate per row:

```
┌─────────────────────────────────────────────────────────────────┐
│ EVIDENCE                          │ PROPOSED CONNECTION         │
│                                   │                             │
│ [1] NCCN Breast Survivorship §3.2 │ joint pain                  │
│     breast-specific               │   — side effect of —        │
│     "<verbatim sentence,          │ aromatase inhibitor         │
│      highlighted in context>"     │                             │
│                                   │ Patient wording:            │
│ [2] ASCO Survivorship §7.1        │ "Some people taking this    │
│     general survivorship          │  pill notice new joint      │
│     "<verbatim sentence>"         │  aches. Has that been true  │
│                                   │  for you?"                  │
├─────────────────────────────────────────────────────────────────┤
│ [Approve] [Reject ▾] [Reword]  Tier B  ☐ Urgent  Prevalence: __ │
│ Origin: literature scan                                         │
└─────────────────────────────────────────────────────────────────┘
```

- Every quotation on screen with the connection, never behind a click, each labelled with source scope. This is the difference between five seconds and three minutes per edge, and it is the entire economics of the feature.
- Keyboard shortcuts for approve / reject / next. Tier A is a batch operation.
- `Reword` edits `patient_phrasing` only.
- **Reject requires a structured reason** (§13.1).
- `Origin` displays `literature scan` or `patient observation` as a bare label with no further detail (§6.4).
- Only a `reviewer_attesting` may clear an urgent flag once set.

### 5.5 Sandbox test chat

Reviewers get a test chat at `/review/sandbox` so they can see how approved connections read in context.

- Runs against a **synthetic sandbox patient** with `is_synthetic = true` and fixture facts. Never a real patient.
- The reviewer may pick which published or draft map version the sandbox loads.
- Sandbox conversations are stored in a separate table and excluded from every analytics and modeler path.
- Test: a session holding only a reviewer role cannot open a chat bound to any `patient_id` where `is_synthetic = false`.

### 5.6 Attestation record

```
attestation
  id, master_edge_id, reviewer_id,
  reviewer_role enum, reviewer_credential enum, reviewer_affiliation enum,
  decision enum, attestation_text_version, attestation_text,
  edge_hash, signed_at, ip_hash
```

Immutable. Reversing a decision means a new attestation; both stay in the trail.

Attestation text for v1, verbatim:

> I attest that this statement is consistent with the cited sources, and that it is appropriate to raise with a patient as a topic to discuss with their care team. I am not attesting that this relationship is true for any individual patient.

That second sentence is what makes it signable. Do not alter without legal review.

`edge_hash` covers the edge **and every evidence row**. Editing either after signing voids the attestation.

### 5.7 Publication gate

`draft → published` requires all of the following, as one transactional check returning an itemized failure list:

- Every edge `status = 'approved'`.
- Every edge has a valid attestation from a reviewer who held `reviewer_attesting` **and** `status = 'active'` at `signed_at`.
- Every `edge_hash` matches current content.
- Every edge has ≥1 evidence row, each still verifying against its source.
- Every referenced concept has `display_patient`.
- Every edge has non-empty `patient_phrasing`.
- No edge uses a type with `enabled_in_version = false`.
- `governance_note` non-null.

On success: freeze `frozen_hash`, stamp publication, supersede the prior version.

### 5.8 PHI boundary without a separate deployment

v2 specified a separate portal application. That is replaced: reviewers work inside the main app, because they also need the sandbox chat and a second deployment doubled the work for a one-reviewer pilot.

The guarantee is preserved at the connection layer instead:

- All `/review/*` request handlers execute on a **dedicated database connection pool** using role `sage_review`.
- `sage_review` holds `SELECT, INSERT, UPDATE` on: `concept`, `source_document`, `master_edge`, `master_edge_evidence`, `master_map_version`, `reviewer`, `reviewer_assignment`, `attestation`, `audit_log`, `extraction_run`, `sandbox_*`.
- `sage_review` holds **zero grants** on `patient_edge`, `patient_edge_event`, and every belief-store or chat table.
- No module under `connection_map/review/` may import a patient model. Enforce with an import-graph test.

Tests, all required:

1. Connect as `sage_review`, assert permission error on `SELECT` from each patient table.
2. Assert every `/review/*` route resolves to the `sage_review` pool.
3. Assert the import-graph rule.
4. Assert a reviewer-only session cannot open a non-synthetic chat.

**This is a weaker guarantee than v2's separate deployment**, because a routing bug could put a review handler on the wrong pool. The four tests above are what close that gap; do not skip them. The tradeoff is deliberate and it is the reason the sandbox chat is possible at all.

Consequence unchanged: a reviewer provably cannot reach patient data, so reviewer onboarding does not require a business associate agreement.

### 5.9 Audit log

```
audit_log     -- append-only
  id, actor_id, actor_role, action, target_table, target_id,
  before_hash, after_hash, metadata jsonb, created_at
```

Every reviewer action, invitation, role change, assignment change, and publication writes a row.

### 5.10 Reviewer independence

For v1 the sole attesting reviewer is the organization's CEO, an MD PhD oncologist. Clinically the right person; also a governance weakness, because the person vouching for the content has an interest in shipping.

- `affiliation` is snapshotted onto every attestation.
- `governance_note` is mandatory at publication. v1 text: *All clinical attestations for this version were provided by an internal reviewer (MD PhD, medical oncology) who is also an officer of the organization. Independent external review is planned before wider release.*
- The workspace shows a standing indicator when a draft has zero external attestations.

**Triggers requiring an external attesting physician before the next publication:**

- any use of the map outside the pilot cohort
- an IRB submission, grant award, or publication relying on this content
- a partnership with a health system, payer, or provider organization
- expansion beyond the pilot cancer

### 5.11 Two-person review

Suspended for v1: the sole reviewer is a medical oncologist with a doctorate, so an NP first pass adds latency without judgment. `reviewer_clinical` stays in the schema unused. Config flag `REQUIRE_CLINICAL_FIRST_PASS_TIER_B` defaults `false`. The code path must exist and be tested while disabled.

---

## 6. Extraction and candidate generation

Three passes. None of them writes an edge without verbatim guideline evidence.

### 6.1 Pass 1 — within-section extraction

```
for each source_document, for each section:
  LLM -> { src_concept_slug, dst_concept_slug, relationship, quoted_sentence }
  reject unless quoted_sentence is an exact substring of the section text
  reject unless both concepts exist in the approved concept table
  reject unless relationship is in the enum
  insert master_edge (tier='A', pass=1, origin='literature_scan') + 1 evidence row
```

The substring check stops fabricated citations. **Do not soften it to fuzzy matching.** The characteristic model failure here is a plausible relationship with an invented citation, and exact matching catches that every time.

### 6.2 Pass 2 — cross-section chaining

```
input: concept list + every verified quotation from pass 1
LLM -> { src, dst, relationship, evidence_ids[], reasoning }
  reject unless every evidence_id exists and is verified
  reject unless >= 2 distinct evidence rows cited
  reject if (src, dst, relationship) already exists
  insert master_edge (tier='B', pass=2, origin='literature_scan') + evidence links
```

Pass 2 reasons over verified quotations, not raw text. It never introduces new quotations.

**Out of scope, deliberately:** cross-cancer analogical inference. It produces confident, plausible, uncitable relationships. Relationships that generalize arrive instead from general survivorship sources as properly cited edges.

### 6.3 Rejected: unconstrained relationship discovery

Do not build a mode where the model is asked what connects to what. Every candidate originates from a quotation or from §6.4, and every candidate terminates in a quotation.

### 6.4 Pass 3 — patient-observation candidates

**Feature flag `PASS3_PATIENT_OBSERVATION`, default OFF. Requires updated consent language and legal sign-off before enabling.**

The idea: a patient starts a treatment and reports a new or worsening symptom. That is a hint about which relationship to go look for in the guidelines. The patient's data proposes a **search query**, never an edge.

```
detect(patient p):                        # single patient, no pooling
  for each (treatment T, symptom S) in p's timeline:
    require: T start recorded, both concepts confirmed facts
    require: S newly reported or worsened AFTER T started
    require: >= MIN_OBS observations of S post-start (default 4)
    require: (T, S) not already in the master map or the candidate queue
    emit ObservationHint{ src_slug: S, dst_slug: T, relationship: side_effect_of }
```

**The hint contains two concept slugs and a relationship type. Nothing else.** No patient identifier, no timing, no counts, no free text, no strength. It is not stored against the patient.

```
resolve(hint):
  run pass-1-style retrieval over the corpus, restricted to this concept pair
  if a verifiable quotation is found:
      insert master_edge (tier per evidence count, pass=3,
                          origin='patient_observation') + evidence rows
  else:
      discard. Do not queue. Do not log the pair.
```

**The resulting edge's evidence is guideline text.** Patient data never becomes evidence and is never stored on the edge. The core guarantee is unchanged.

Privacy controls, all mandatory:

- **k-anonymity suppression.** Do not emit a hint unless at least `K_MIN` patients (default 5) have the source treatment as a confirmed fact. Below that threshold, a hint reaching a reviewer would implicitly disclose that a specific patient exists on a rare treatment with a specific symptom. This is a count-only query and is one of the two aggregation exceptions permitted in §0 rule 2.
- **Rate limit.** At most `MAX_HINTS_PER_PATIENT_PER_MONTH` (default 3).
- **Origin label only.** The review workspace shows `Origin: patient observation` and nothing more. Never a count, a date, a cohort size, or a patient reference.
- **No reverse lookup.** No table links a published edge back to the patients whose data produced its hint. Do not build one for debugging.

Honest limitation to record here: with a cohort in the tens, `K_MIN = 5` will suppress nearly every hint. Pass 3 produces close to nothing until the cohort grows. Build it, flag it off, and expect it to stay quiet through v1.

---

## 7. Runtime

### 7.1 Instantiator

Runs on belief-store change or on publication of a new version.

```
patient_edges(p) = { e ∈ published_master_map(p.cancer) :
                     e.relationship is enabled
                     AND src(e) ∈ confirmed_facts(p)
                     AND dst(e) ∈ confirmed_facts(p) }
```

**Both endpoints must be `confirmed`, not `provisional`.** New matches created `instantiated` with priors copied. Retracted endpoints move edges to `retired`, never deleted.

The restrictiveness is the point: the patient map never proposes a relationship the literature has not licensed. That is pre-registration by construction, and it removes the multiple-comparisons problem an unconstrained n=1 correlation search would create.

### 7.2 Proposer

On the scheduled modeler pass, score `instantiated` edges: endpoint recency and salience, whether the symptom was recently reported, lifecycle stage (never during `getting_to_know_you`), cooldown from `ask_count` / `last_asked_at`. Weights live in `config/scoring.yaml`.

### 7.3 Question policy integration

Register type `connection_confirm`. Do **not** modify arbitration logic. On selection: set `proposed`, stamp, increment, create `question_instance_id`, render `patient_phrasing` with yes / no / not sure.

### 7.4 Response handler

```
on response(question_instance_id, answer):
  if already processed: return
  yes      -> alpha += 1; status = 'confirmed'
  no       -> beta  += 1; status = 'refuted'
  not_sure -> status = 'instantiated'; cooldown
  skip     -> status = 'instantiated'; cooldown
  append patient_edge_event
```

"Not sure" is a first-class answer and must not be coerced. A patient who does not know is giving real information.

### 7.5 Consumers

- **Chat context** — confirmed edges serialized into the RAG prompt as neutral statements, never as instructions to assert a link.
- **Check-in selection** — confirmed edges bias which wellness questions get asked.
- **Trial ranking** — optional features, behind a flag, off by default in v1.

---

## 8. Patient-facing copy rules

Enforced by lint and unit test over `patient_phrasing` and every generated string:

- Reading level at or below grade 6.
- **No em dashes.** Use a period, a comma, or a new sentence. Applies to every patient-facing string including onboarding, questions, and revision copy.
- No causal verbs: `causes`, `leads to`, `results in`, `because of`, `due to`, `triggers`.
- Permitted framings: "some people ... notice", "often go together", "may be worth mentioning to your care team".
- No numerals expressing confidence or probability.
- No clinical jargon in `display_patient`. "hormone pill", not "aromatase inhibitor".
- Answerable yes / no / not sure by someone with no medical training.

A patient-facing string failing any of these fails CI.

---

## 9. Patient honesty commitment

Signal quality depends on patients understanding that "no" is as useful as "yes." People asked a question by a helpful system drift toward agreement. The countermeasure is not deception, it is telling them plainly what honest answers are for.

### 9.1 Onboarding screen

A dedicated step. Not a checkbox inside terms of service.

```
honesty_commitment
  id, patient_id, copy_version, accepted_at,
  surface enum   -- 'onboarding' | 'first_connection_question'
```

Copy for v1 (grade 6, no em dashes, no penalty framing):

> **Your honest answers are what make this work.**
>
> Sometimes we will ask if something is true for you. For example, whether your tiredness and your sleep seem to go together.
>
> There are no right or wrong answers. Saying **no** helps us just as much as saying **yes**. Saying **not sure** is fine too.
>
> If we get something wrong, telling us so is the most useful thing you can do. You can change any answer later.

- Cannot be skipped. Acceptance is a single tap. No quiz, no scroll gate.
- `copy_version` recorded so confirmation behavior can be compared across wordings.
- Re-shown once, shortened, immediately before the first connection question. Onboarding is forgotten within a week.
- Never shown again after that. Repeating it reads as an accusation.

### 9.2 In-question reinforcement

Every connection question renders a persistent line beneath the chips: *No is just as helpful as yes.* Static copy. No A/B testing on a cohort this small.

### 9.3 Patient-initiated revision

The onboarding copy promises patients they can change any answer, so the path must exist.

- A "things I've told you" view lists confirmed and refuted connections in plain language.
- Each row offers "actually, that is not right for me" / "actually, that is right for me."
- Revision flips status, adjusts Beta counts, appends a `patient_revision` event.
- Not routed through the question policy. Does not count against `ask_count`.
- No limit, no friction, no confirmation dialog.

---

## 10. Breast cancer v1 content

Everything below is an **extraction target**, not approved content. Each must be found in the corpus with a verifiable quotation and signed by the attesting physician before it can ship. The list exists so the extractor and the review queue have a scoped target, and so coverage gaps are visible early.

### 10.1 Concepts

**biomarker** — ER status, PR status, HER2 status, Ki-67, menopausal status
**treatment** — aromatase inhibitor, tamoxifen, ovarian suppression, anthracycline chemotherapy, taxane chemotherapy, trastuzumab, radiation therapy, bisphosphonate or denosumab
**procedure** — lumpectomy, mastectomy, sentinel node biopsy, axillary node dissection, breast reconstruction
**symptom** — joint pain, muscle pain, hot flashes, night sweats, fatigue, peripheral neuropathy (numbness or tingling in hands and feet), balance problems, falls, nausea, hair loss or thinning, lymphedema (arm swelling or heaviness), vaginal dryness, painful intercourse, low libido, cognitive complaints (memory, concentration, word finding), cardiac symptoms (breathlessness, swelling, palpitations), fever, vaginal bleeding, leg pain or swelling, arm redness or warmth, weight gain, general pain
**lab_or_measure** — LVEF, bone mineral density, neutrophil count, vitamin D, body weight
**daily_life** — sleep quality, mood, anxiety, physical activity, appetite, sexual health, work status, taking the pill as prescribed

### 10.2 Extraction targets — treatment side effects

| src (symptom) | dst (treatment) | urgency | note |
|---|---|---|---|
| joint pain | aromatase inhibitor | routine | most common AI side effect, near half of patients |
| muscle pain | aromatase inhibitor | routine | |
| hot flashes | aromatase inhibitor | routine | |
| night sweats | aromatase inhibitor | routine | |
| vaginal dryness | aromatase inhibitor | routine | tends to persist rather than fade |
| painful intercourse | aromatase inhibitor | routine | |
| low libido | aromatase inhibitor | routine | |
| bone mineral density loss | aromatase inhibitor | routine | drives fracture risk |
| hair thinning | aromatase inhibitor | routine | |
| sleep quality | aromatase inhibitor | routine | insomnia increasingly recognized |
| cognitive complaints | aromatase inhibitor | routine | endocrine-therapy CRCI |
| hot flashes | tamoxifen | routine | |
| night sweats | tamoxifen | routine | |
| sleep quality | tamoxifen | routine | |
| cognitive complaints | tamoxifen | routine | memory, verbal fluency, processing speed |
| mood | tamoxifen | routine | |
| vaginal bleeding | tamoxifen | **urgent** | endometrial evaluation |
| leg pain or swelling | tamoxifen | **urgent** | venous thromboembolism |
| hot flashes | ovarian suppression | routine | |
| bone mineral density loss | ovarian suppression | routine | |
| fatigue | anthracycline chemotherapy | routine | |
| nausea | anthracycline chemotherapy | routine | |
| hair loss | anthracycline chemotherapy | routine | |
| cognitive complaints | anthracycline chemotherapy | routine | very commonly reported after chemotherapy |
| LVEF decline | anthracycline chemotherapy | routine | lab-side, not patient-visible |
| cardiac symptoms | anthracycline chemotherapy | **urgent** | can present late, years after treatment |
| fever | anthracycline chemotherapy | **urgent** | neutropenic fever |
| peripheral neuropathy | taxane chemotherapy | routine | most common dose-limiting toxicity |
| balance problems | taxane chemotherapy | routine | |
| joint pain | taxane chemotherapy | routine | |
| muscle pain | taxane chemotherapy | routine | |
| fatigue | taxane chemotherapy | routine | |
| LVEF decline | trastuzumab | routine | risk rises with prior anthracycline |
| cardiac symptoms | trastuzumab | **urgent** | |
| fatigue | radiation therapy | routine | |
| skin changes | radiation therapy | routine | |
| lymphedema | radiation therapy | routine | axillary or regional nodal irradiation |
| lymphedema | axillary node dissection | routine | roughly a fifth to a third of patients |
| arm redness or warmth | lymphedema | **urgent** | possible cellulitis |
| numbness near the scar | axillary node dissection | routine | |
| numbness near the scar | mastectomy | routine | |

### 10.3 Extraction targets — co-occurrence

The psychoneurological symptom cluster is the best-supported material in the general survivorship literature and should be the backbone of the `co_occurs_with` set.

| a | b | note |
|---|---|---|
| fatigue | sleep quality | core cluster pair |
| fatigue | mood | core cluster pair |
| fatigue | anxiety | |
| fatigue | general pain | |
| fatigue | cognitive complaints | |
| sleep quality | general pain | |
| sleep quality | mood | |
| sleep quality | hot flashes | vasomotor symptoms disrupt sleep |
| sleep quality | cognitive complaints | |
| mood | anxiety | |
| mood | cognitive complaints | |
| joint pain | physical activity | |
| fatigue | physical activity | |
| peripheral neuropathy | balance problems | |
| balance problems | falls | |
| lymphedema | work status | |
| joint pain | taking the pill as prescribed | joint pain is a leading reason women stop endocrine therapy |
| hot flashes | taking the pill as prescribed | |
| sleep quality | taking the pill as prescribed | |
| general pain | work status | |
| fatigue | work status | |

### 10.4 Extraction targets — later relationship types

Not enabled in v1. Extract and review them anyway, so v1.1 ships by flipping a flag rather than by running another review cycle.

**`monitored_with`** — aromatase inhibitor / bone mineral density · trastuzumab / LVEF · anthracycline chemotherapy / LVEF · tamoxifen / annual gynecologic assessment
**`mitigated_by`** — fatigue / physical activity · joint pain / physical activity · lymphedema / arm exercise and skin care · sleep quality / sleep routine
**`indicated_by`** — ER status / aromatase inhibitor · ER status / tamoxifen · HER2 status / trastuzumab · menopausal status / aromatase inhibitor versus tamoxifen

### 10.5 Launch scope

Approve as many as review time allows. **Launch with 12 to 15 live**, weighted toward the endocrine-therapy side effects and the core symptom cluster, since those are the highest-prevalence and most actionable. The map is versioned config; adding edges later is the architecture working.

---

## 11. Synthetic validation

Zero patients at build time, so the loop is proven against generated data first. Build `tests/synthetic/` as a real harness.

```
generate_cohort(n, map_version):
  sample a plausible fact set per synthetic patient
  sample a ground-truth subset T of edges "actually true for them"
  write facts into a test belief store

simulate_answers(patient, edge, params):
  if edge ∈ T:  P(yes) = params.sensitivity        # default 0.85
  else:         P(yes) = params.acquiescence_rate  # default 0.15
  small probability of 'not sure'
```

Assertions:

1. Instantiation produces exactly the edges with both endpoints confirmed, no more and no fewer.
2. After k answers, Beta point estimates for edges in T separate from those outside T.
3. No illegal state transition across the run.
4. No urgent edge reaches `proposed`.
5. Raising `acquiescence_rate` degrades separation predictably. This tells you the noise level at which the loop stops being informative, and it is the number §13.2 will be checked against.
6. Revision events restore correct counts.
7. With the feature flag off, chat output is identical to baseline (§0.1).

---

## 12. Build phases

Phases 1 through 6 need no patients. Phases 1 through 4 need no clinician.

| Phase | Deliverable | Gate |
|---|---|---|
| 1 | Schema, migrations, concept seed, corpus ingest | migrations clean |
| 2 | Reviewer roles, `sage_review` pool, audit log | **all four §5.8 tests pass** |
| 3 | Review workspace, attestation, publication gate, governance note | a human approves an edge end to end |
| 4 | Extraction pass 1 and pass 2 over both corpora | ≥60 candidates with verified evidence |
| 5 | *(human — clinical review, budget 3 to 4 hours)* | v1 map published |
| 6 | Synthetic validation harness | all seven assertions pass |
| 7 | Instantiator, proposer, question policy integration | edges appear on synthetic patients |
| 8 | Response handler, Beta updates, events, revision path | full loop green |
| 9 | Honesty commitment, onboarding, in-question copy | copy lint passes |
| 10 | Sandbox test chat for reviewers | reviewer walks a synthetic conversation |
| 11 | Consumers behind flags | — |
| 12 | First real patients | — |
| 13 | Pass 3, flag off, pending consent and legal sign-off | — |

**Note on phase 10.** A physician clicking through the sandbox validates that questions read sensibly and the flow works. It does **not** validate that patients answer honestly, because a clinician role-playing a patient is not one. Record it as face validity. Claims about signal quality wait for phase 12.

---

## 13. Metrics

### 13.1 Extractor quality

The attesting physician's rejections are the only real evaluation signal the pipeline has, and they are produced free as a byproduct of review. Capture them.

`rejection_reason` is a **mandatory structured enum**:

| Reason | What it indicts |
|---|---|
| `quote_does_not_support` | the model misread its own citation |
| `quote_out_of_context` | present, but meaning changed |
| `too_general` | true but not useful to a patient |
| `wrong_relationship_type` | vocabulary mapping error |
| `not_appropriate_for_patients` | correct but should not be surfaced |
| `clinically_incorrect` | wrong regardless of source |
| `duplicate` | dedup failure |
| `chain_does_not_hold` | pass 2 or 3: quotations do not combine |

Report per run, split by pass and tier. The mix tells you what to fix: `quote_does_not_support` means tighten the prompt, `too_general` means tighten concept granularity, `chain_does_not_hold` means pass 2 is over-reaching.

Healthy target: under 25% rejection on Tier A. Expect Tier B considerably higher at first.

### 13.2 Acquiescence monitor

Where a reviewer recorded `expected_prevalence_low/high`, compare observed confirmation rate against that band. A relationship the literature puts near 30% that 90% of patients confirm indicates the yes/no signal is measuring agreeableness rather than experience.

- Population-level, therefore one of the two aggregation exceptions in §0 rule 2. Implement as an internal metrics job over a **count-only view**. Never through the learning loop, never producing patient-identifiable output.
- Do not run below 20 responses per edge. Log as unavailable rather than reporting noise.
- If the signal degrades, the remedy is copy and question design, not discarding data.

---

## 14. Acceptance criteria

Write these before the code they cover.

1. `sage_review` role raises a permission error on `SELECT` from every patient table.
2. Every `/review/*` route resolves to the `sage_review` connection pool.
3. No module under `connection_map/review/` imports a patient model.
4. A reviewer-only session cannot open a chat bound to a non-synthetic patient.
5. A single account cannot hold both a reviewer role and a patient record.
6. Publication fails, itemized, when any edge lacks a valid attestation.
7. Publication fails when the attesting reviewer was `revoked` at `signed_at`.
8. Publication succeeds when the reviewer was active at `signed_at` but revoked afterward.
9. Publication fails when `governance_note` is null.
10. Mutating a master edge **or any evidence row** after signing voids the attestation.
11. Pass 1 rejects any candidate whose `quoted_sentence` is not an exact substring of its section.
12. Pass 2 rejects candidates citing fewer than two verified evidence rows.
13. A master edge with zero evidence rows cannot be inserted.
14. Pass 3 emits nothing when fewer than `K_MIN` patients have the source treatment.
15. Pass 3 discards any hint that finds no verifiable quotation, and writes no record of the pair.
16. No table links a published edge to the patients whose data produced its hint.
17. No `patient_edge` exists whose master edge is absent from a published version.
18. An edge does not instantiate when one endpoint is `provisional`.
19. An `urgent` edge never reaches `status = 'proposed'`.
20. The same `question_instance_id` submitted twice increments `alpha` exactly once.
21. A `refuted` edge is never re-proposed by the question policy within a version.
22. Patient revision flips status and adjusts Beta counts correctly in both directions.
23. Every patient-facing string passes the copy lint in §8, including the em dash rule.
24. Onboarding cannot complete without an `honesty_commitment` row.
25. `attestation` and `audit_log` reject `UPDATE` and `DELETE` at the database level.
26. `rejection_reason` is non-null on every rejected edge.
27. No module in this feature imports from the learning-loop package.
28. With the feature flag off, chat output is identical to the pre-feature baseline.
29. All seven synthetic-validation assertions pass.

---

## 15. Repo layout

```
connection_map/
  models/          concept.py  source_document.py  master_edge.py
                   evidence.py  patient_edge.py  attestation.py
  extraction/      pass1_section.py  pass2_chain.py  pass3_observation.py
                   citation_check.py  tiering.py
  review/          queue.py  attest.py  publish.py  gates.py
                   governance.py  sandbox.py  db.py   # sage_review pool
  runtime/         instantiate.py  propose.py  respond.py  revise.py  fallback.py
  consumers/       chat_context.py  checkin.py  trial_features.py
  copy/            lint.py  phrasing_rules.py  honesty_commitment.py
  metrics/         extractor_quality.py  acquiescence.py
  config/          concepts_breast.yaml  scoring.yaml  attestation_text.yaml
                   honesty_copy.yaml  corpus_manifest.yaml  flags.yaml
  migrations/
  tests/
    synthetic/     cohort.py  simulate.py  assertions.py
```

---

## 16. Notes for the coding agent

- Build phases in order. The four §5.8 tests gate everything after phase 2.
- Write the guardrail tests (§14) before the code they guard. They encode the compliance argument, not just correctness.
- Prefer database-level enforcement wherever a constraint can be expressed either way: check constraints, row-level policies, revoked grants, append-only triggers. Application logic is easier to bypass and harder to demonstrate to a reviewer.
- Clinical logic and patient-facing copy go in `config/` as reviewable data, following the precedent set by the safety classifier JSON. Do not bury thresholds, weights, or strings in Python.
- The citation checks are exact string matching. Any proposal to relax them to embeddings, fuzzy matching, or LLM-as-judge is a rejection of the feature's core guarantee. Do not.
- Pass 3 ships flag-off. Do not enable it, do not write a migration that enables it, and do not build the reverse-lookup table that would make debugging it convenient.
- When something here is ambiguous, stop and ask rather than choosing. Especially anything touching attestation, publication, PHI boundaries, pass 3, or patient-facing copy.
- Do not add features not specified here. Specifically excluded, each having been requested before: admin override on publication, bulk-approve-all, previewing unpublished edges on a real patient, and any cross-patient query outside §6.4's k-check and §13.2's count-only view.
