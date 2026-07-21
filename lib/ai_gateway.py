# ai_gateway.py
"""
Per-call LLM telemetry (supervisor gateway mandate 2026-07-21):
"Log task, provider, model, latency, and token counts on every call, so we
can compare quality and cost per task and reroute in config."

One structured log line per provider call — NON-PHI SCALARS ONLY (never
prompt or response text), so the no-PHI-in-logs rule is untouched. Grep for
`AI_CALL` in Vercel logs to compare latency/cost per task and feed routing
decisions in lib/model_registry.py.

This is deliberately a thin seam, not an abstraction layer: call sites keep
their provider clients and payloads (see docs/sage-implementation-guidelines-
notes.md on the Flask-boundary question) and add one `log_llm_call(...)`
after each call.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Task vocabulary (superset of the guidelines' chat|extract|summarize|classify
# to keep existing pipeline segments distinguishable).
TASKS = ("chat", "extract", "summarize", "classify", "verify", "subquery",
         "modeler")


def log_llm_call(
    task: str,
    provider: str,
    model: str,
    latency_ms: int,
    usage: Optional[Any] = None,
    *,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    ok: bool = True,
) -> None:
    """Emit the AI_CALL telemetry line. Never raises.

    `usage` accepts the provider response's usage object (OpenAI-style
    attributes or dict); explicit token kwargs win over it.
    """
    try:
        if usage is not None:
            if prompt_tokens is None:
                prompt_tokens = (getattr(usage, "prompt_tokens", None)
                                 if not isinstance(usage, dict)
                                 else usage.get("prompt_tokens"))
            if completion_tokens is None:
                completion_tokens = (getattr(usage, "completion_tokens", None)
                                     if not isinstance(usage, dict)
                                     else usage.get("completion_tokens"))
        logger.info(
            "AI_CALL task=%s provider=%s model=%s latency_ms=%d "
            "ptok=%s ctok=%s ok=%s",
            task, provider, model, int(latency_ms),
            prompt_tokens if prompt_tokens is not None else "-",
            completion_tokens if completion_tokens is not None else "-",
            ok,
        )
    except Exception:
        pass
