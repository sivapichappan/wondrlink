# model_registry.py
"""
Central model registry: one place for every LLM model ID the pipeline uses.

Each pipeline segment has a default model and an env-var override, so swapping
a model is a Vercel env change (instantly revertible), never a code change.

Segments
--------
chat       The patient-facing conversation model (Together). The app's voice.
extractor  Structured fact extraction from chat turns (Together, JSON mode).
verifier   Response verification / small utility calls (Groq, fast + cheap).
fallback   Chat fallback when Together is unavailable (Groq).
modeler    RESERVED for the future connections-layer Modeler (no caller yet).

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
    # Sage voice (Workstream C, 2026-07-18): chat moved to Claude Sonnet.
    # Requires ANTHROPIC_API_KEY at runtime; when the key is absent the call
    # path falls back to chat_together automatically, so deploys are safe
    # before the key lands. Rollback = MODEL_CHAT_PROVIDER=together.
    "chat": {
        "provider": "anthropic",
        "default": "claude-sonnet-5",
        "env": "MODEL_CHAT",
    },
    # The Together-side chat model: primary when chat provider is 'together',
    # first fallback when the anthropic call is unavailable/fails.
    "chat_together": {
        "provider": "together",
        "default": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
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
    "fallback": {
        "provider": "groq",
        "default": "llama-3.1-8b-instant",
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
