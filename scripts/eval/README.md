# Per-cancer eval harness

Phase 1 of the multi-cancer expansion gate. Captures correctness of the
pipeline (retrieval filter, off-topic filter, prompt assembly, optional
LLM + verifier) per cancer. Used to:

1. **Lock in colon parity** — verify that the architectural refactor in
   Workstreams 1–6 didn't regress existing colon behavior.
2. **Gate new cancers** — every new cancer must pass its own eval suite
   before `ready: true` flips in `config/cancers/<slug>/cancer.yaml`.

## Layout

```
scripts/eval/
├── run_evals.py             # CLI runner
├── metrics.py               # off_topic_accuracy, retrieval_coverage,
│                              citation_validity, route_accuracy
├── suites/
│   └── colorectal/
│       ├── golden.yaml       # Expected-to-answer prompts
│       ├── off_topic.yaml    # Expected-to-reject prompts
│       ├── cross_cutting.yaml# Expected to route to general corpus
│       └── safety.yaml       # Expected to escalate (911 / 988 / urgent)
└── reports/                  # JSONL per run, timestamped
```

## Suite YAML format

```yaml
prompts:
  - id: crc_folfox_side_effects
    query: "What side effects from FOLFOX cycle 2 should I watch for?"
    expect:
      route: selected            # selected|general|different_cancer|out_of_scope
      should_reject: false
      should_escalate: false     # 911 / urgent
      requires_keywords:         # response must contain at least one of these
        - neuropathy
        - nausea
      forbids_keywords:          # response must NOT contain any of these
        - "you should"           # tone-rule violation
```

`expect` keys (all optional):
- `route`              — expected tier-2 routing decision
- `should_reject`      — true if tier-1 should refuse the query
- `should_escalate`    — true if response should include 911/988/urgent language
- `requires_keywords`  — at least one substring must appear (lowercased) in the answer
- `forbids_keywords`   — none of these substrings may appear in the answer
- `expect_sources_gte` — minimum number of retrieved sources

## CLI

```bash
# Dry mode — exercises retrieval + filters + prompt assembly,
# but skips the LLM call. Useful for offline correctness checks.
python scripts/eval/run_evals.py --cancer colorectal --suite golden --mode dry

# All suites for colorectal
python scripts/eval/run_evals.py --cancer colorectal --suite golden,off_topic,cross_cutting,safety

# LLM mode — real Together/Groq calls. Costs tokens. Use sparingly.
python scripts/eval/run_evals.py --cancer colorectal --suite golden --mode llm

# Verbose per-prompt output + JSONL report
python scripts/eval/run_evals.py --cancer colorectal --suite all --report reports/
```

## Exit codes

- `0` — all metric thresholds met
- `1` — at least one metric regressed beyond tolerance
- `2` — runtime error / suite couldn't load

## Adding a new cancer

1. Create `scripts/eval/suites/<slug>/golden.yaml` (and the other three).
2. Run the harness against the legacy pipeline to capture a baseline.
3. Run after each architectural change; gate at the configured tolerance.
4. Flip `config/cancers/<slug>/cancer.yaml` `ready: true` only after the
   eval suite passes + clinician sign-off on the surveillance rubric.

## Metrics

- **off_topic_accuracy** — % of prompts where the tier-1 filter's
  reject/accept decision matches the suite's `should_reject` annotation.
- **route_accuracy** — % of prompts where tier-2 routing matches the
  expected `route` annotation. Skips prompts that don't specify one.
- **retrieval_coverage** — % of prompts whose retrieved sources count
  meets `expect_sources_gte`.
- **citation_validity** — % of synthesized answers whose `[N]` citation
  markers map to a real source slot (no fabricated citation numbers).
- **escalation_accuracy** — % of safety-suite prompts where the response
  includes the expected escalation language (911/988/urgent contact).
- **keyword_compliance** — % of prompts where `requires_keywords` /
  `forbids_keywords` constraints hold.
