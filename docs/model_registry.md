# Model registry

All LLM model IDs live in `lib/model_registry.py` — one segment per pipeline role,
each overridable by an env var. **Never hardcode a model ID at a call site.**

| Segment | Default | Env override | Used by |
|---|---|---|---|
| `chat` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | `MODEL_CHAT` | `call_llm` primary (the app's voice) |
| `extractor` | `openai/gpt-oss-120b` | `MODEL_EXTRACTOR` | profile fact extraction (JSON mode) |
| `verifier` | `llama-3.1-8b-instant` (Groq) | `MODEL_VERIFIER` | response verification, subquery derivation |
| `fallback` | `llama-3.1-8b-instant` (Groq) | `MODEL_FALLBACK` | chat fallback when Together is down |
| `modeler` | `deepseek-ai/DeepSeek-V4-Pro` | `MODEL_MODELER` | RESERVED — future connections-layer Modeler |

## Swapping the chat model (e.g. evaluating `moonshotai/Kimi-K2.6`)

1. Set `MODEL_CHAT=<candidate>` in a Vercel **preview** environment only.
2. Against the preview run:
   - `python3 scripts/eval/run_evals.py --cancer <each of the 10> --suite all --mode llm`
   - `python3 scripts/test_all_features.py`
   - `python3 scripts/test_pii_guard.py`
   - `python3 scripts/test_clinical_trials_live.py`
3. Diff the JSONL eval reports against the current-model baseline. Reports embed
   `get_registry_snapshot()`, so every run is attributable to its models.
4. All thresholds pass → set `MODEL_CHAT` in production. Rollback = unset the var.

**Rule: one variable per eval window.** Never land a chat-model swap and a prompt
change in the same window — regressions become unattributable.

## De-identification invariant

Every segment's calls must respect `.claude/rules/backend-python.md`: patient data
passes through `lib/deidentify.py` before reaching Together/Groq, and the PII leak
guard (`detect_pii_leaks`) scans the PHI-bearing payload. The extractor builds its
profile context via `_extraction_profile_context()` in `lib/llm_utils.py`, which
de-identifies, strips bookkeeping (`_sources`, `beliefs`, `model_state`, recaps),
and omits the context entirely if the guard trips.

## Chat provider chain (Workstream C, 2026-07-18)

Chat voice = `claude-sonnet-5` (Anthropic Messages API, plain requests, no SDK).
Chain: anthropic -> chat_together (Llama-3.3-70B) -> groq. No ANTHROPIC_API_KEY =
automatic Together fallback, so deploys are safe before the key lands.
Rollback without deploy: `MODEL_CHAT_PROVIDER=together`. Full llm-mode eval
battery + cost readout REQUIRED once ANTHROPIC_API_KEY is set (one variable
per eval window - no prompt changes in the same window).
