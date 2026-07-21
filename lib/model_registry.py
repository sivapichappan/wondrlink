# model_registry.py
"""
Central model registry: one place for every LLM model ID the pipeline uses.

Each pipeline segment has a default model and an env-var override, so swapping
a model is a Vercel env change (instantly revertible), never a code change.

Segments
--------
chat        The patient-facing conversation model (Together). The app's voice.
extractor   Structured fact extraction from chat turns (Together, JSON mode).
verifier    Response verification / small utility calls (Groq, fast + cheap).
classifier  Pre-chat safety tiering of every inbound message (Groq, fast).
fallback    Chat fallback when Together is unavailable (Groq).
modeler     Connections-layer Modeler (background reasoning, Together).

Chat-model swap procedure (e.g. evaluating moonshotai/Kimi-K2.6)
----------------------------------------------------------------
1. Set MODEL_CHAT=<candidate> in a Vercel PREVIEW environment only.
2. Against the preview, run:
     python3 scripts/eval/run_evals.py --cancer <each cancer> --suite all --mode llm
     python3 scripts/test_all_features.py
     python3 scripts/test_pii_guard.py
     python3 scripts/test_clinical_trials_live.py
3. Diff the JSONL eval reports vs. the current-model baseline (reports embed
   get_registry_snapshot(), so every run is attributable to its models).
4. All thresholds pass -> set MODEL_CHAT in production. Rollback = unset it.
NEVER swap the chat model and change the prompt in the same eval window —
one variable at a time, or regressions can't be attributed.
"""

import os
from typing import Dict

# segment -> (provider, default model id, env override var)
_SEGMENTS: Dict[str, Dict[str, str]] = {
    # Sage voice (final decision 2026-07-18): Kimi-K2.6 on Together — the
    # strongest conversational model on the platform at interactive speed.
    # The Anthropic path stays built + dormant: MODEL_CHAT_PROVIDER=anthropic
    # + MODEL_CHAT=claude-sonnet-5 + ANTHROPIC_API_KEY re-enables it with no
    # deploy. Rollback to the previous voice: MODEL_CHAT=meta-llama/Llama-3.3-70B-Instruct-Turbo.
    "chat": {
        "provider": "together",
        "default": "moonshotai/Kimi-K2.6",
        "env": "MODEL_CHAT",
    },
    # The Together-side chat model when the primary chat provider is NOT
    # together (e.g. anthropic primary -> this is the first fallback voice).
    "chat_together": {
        "provider": "together",
        "default": "moonshotai/Kimi-K2.6",
        "env": "MODEL_CHAT_TOGETHER",
    },
    "extractor": {
        "provider": "together",
        "default": "openai/gpt-oss-120b",
        "env": "MODEL_EXTRACTOR",
    },
    "verifier": {
        "provider": "groq",
        "default": "llama-3.1-8b-instant",
        "env": "MODEL_VERIFIER",
    },
    # Pre-chat safety classifier (supervisor mandate 2026-07-21): tiers every
    # inbound message against config/safety/ rules BEFORE the chat model.
    # Groq 70B-versatile won the 2026-07-21 bake-off: 10/10 tier accuracy,
    # p50 ~0.6s (Together 70B-Turbo: same accuracy, p50 ~2s; 8B/20B-class
    # and reasoning models mis-tiered or truncated). Groq rate limits are
    # PER-MODEL, so this rides the 70b-versatile 12k-TPM bucket, separate
    # from the 8B verifier. Alternate via MODEL_CLASSIFIER_PROVIDER=together
    # + MODEL_CLASSIFIER=meta-llama/Llama-3.3-70B-Instruct-Turbo.
    "classifier": {
        "provider": "groq",
        "default": "llama-3.3-70b-versatile",
        "env": "MODEL_CLASSIFIER",
    },
    # Emergency chat backup when Together is down. 70B on Groq is still
    # near-instant, so the backup is no longer a quality cliff (2026-07-18).
    "fallback": {
        "provider": "groq",
        "default": "llama-3.3-70b-versatile",
        "env": "MODEL_FALLBACK",
    },
    # Reserved for the future connections-layer Modeler (background reasoning
    # over the full patient record). No production caller yet.
    "modeler": {
        "provider": "together",
        "default": "deepseek-ai/DeepSeek-V4-Pro",
        "env": "MODEL_MODELER",
    },
}


def get_model(segment: str) -> str:
    """Model ID for a pipeline segment (env override wins over default)."""
    seg = _SEGMENTS.get(segment)
    if seg is None:
        raise KeyError(f"Unknown model segment: {segment!r}")
    return os.getenv(seg["env"], seg["default"])


def get_provider(segment: str) -> str:
    """Provider name ('anthropic' | 'together' | 'groq') for a segment.
    Env-overridable via <ENV>_PROVIDER (e.g. MODEL_CHAT_PROVIDER=together
    rolls the chat voice back to Together without a deploy)."""
    seg = _SEGMENTS.get(segment)
    if seg is None:
        raise KeyError(f"Unknown model segment: {segment!r}")
    return os.getenv(seg["env"] + "_PROVIDER", seg["provider"])


def get_registry_snapshot() -> Dict[str, str]:
    """Resolved segment->model map, for eval report headers / health debug."""
    return {name: get_model(name) for name in _SEGMENTS}
