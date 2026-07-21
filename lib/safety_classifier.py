# safety_classifier.py
"""
Pre-chat safety classifier (supervisor mandate 2026-07-21).

Runs on EVERY inbound chat message BEFORE the chat model:
  1. The deterministic keyword floor (lib/safety_rules.deterministic_match)
     ALWAYS runs — zero latency, survives provider outages.
  2. If enabled, one fast LLM call (registry segment "classifier", Groq 8B)
     applies the supervisor's AI-judgment-fallback rules: symptom
     combinations, paraphrases, caregiver phrasing, context modifiers.
  3. The two results merge via tier_max — the LLM can RAISE the tier the
     floor found, never lower it. Any LLM failure falls open to the floor
     result (err-toward-escalation governs the LLM's own uncertainty, not
     outages; a NONE-on-outage still passes through the downstream
     symptom-urgency prompt injection as backstop).

PHI invariant (deliberate deviation from the rules file's classifier
contract, which lists patient_name as an input): the LLM receives ONLY the
already-sanitized message text plus two non-identifying scalars
(on_active_treatment, perspective). patient_name NEVER reaches any provider;
the caregiver-voice patient_line is rendered server-side by
render_patient_line() AFTER classification. See
docs/sage-implementation-guidelines-notes.md.

Kill switch: SAFETY_CLASSIFIER_ENABLED, read directly from env, DEFAULT ON.
This deliberately deviates from the dormant-flag default-false rule because
it is a live safety feature the moment it ships (its merge is gated on the
safety eval suite), not a dormant one. Setting it to "false" in Vercel
reverts to floor-only classification, which is a strict superset of the old
detect_crisis_pattern behavior.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from safety_rules import (
    deterministic_match,
    emergency_number,
    load_safety_rules,
    tier_max,
)

logger = logging.getLogger(__name__)

_PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "files" / "classify.md"

# Groq 70b-versatile: p50 ~0.6s, max ~1.7s measured 2026-07-21 on the
# condensed prompt. The chat endpoint runs classification concurrently with
# retrieval, so the typical added wall-clock is ~0. The cap bounds a hang
# before falling open to the deterministic floor.
_LLM_TIMEOUT_SECONDS = 3.5
_LLM_MAX_TOKENS = 250

_VALID_TIERS = {"T1", "T2", "T3", "MH", "NONE"}


@dataclass
class SafetyResult:
    tier: str
    category: str
    confidence: float
    rationale: str
    rule_matched: bool
    source: str  # 'rules' | 'llm' | 'merged' | 'rules-fallback' | 'none'
    model: Optional[str] = None
    latency_ms: Optional[int] = None


_NONE_RESULT_ARGS: Dict[str, Any] = {
    "tier": "NONE",
    "category": "",
    "confidence": 0.0,
    "rationale": "",
    "rule_matched": False,
}


def classifier_enabled() -> bool:
    """Kill switch — env-direct read, default ON (see module docstring)."""
    return os.getenv("SAFETY_CLASSIFIER_ENABLED", "true").strip().lower() != "false"


@lru_cache(maxsize=1)
def _prompt_template() -> str:
    return _PROMPT_FILE.read_text()


def _build_system_prompt(on_active_treatment: bool, perspective: str) -> str:
    # MINIMAL reference: category names grouped by tier. The full trigger
    # lists are enforced deterministically by the keyword floor before this
    # call, and the tier definitions in the prompt template carry the
    # clinical content — repeating the trigger JSON here tripled prompt
    # size, blew Groq's TPM budget, and pushed Together prefill latency
    # into timeout territory (all measured 2026-07-21). The LLM's job is
    # judgment BEYOND the list; category anchors are what it needs.
    rules = load_safety_rules()
    rules_ref: Dict[str, list] = {}
    for r in rules.get("rules") or []:
        tier = r.get("tier")
        cat = r.get("category")
        if tier and cat and cat not in rules_ref.setdefault(tier, []):
            rules_ref[tier].append(cat)
    return (
        _prompt_template()
        .replace("<<RULES_JSON>>", json.dumps(rules_ref, separators=(",", ":")))
        .replace("<<EMERGENCY_NUMBER>>", emergency_number())
        .replace("<<ON_ACTIVE_TREATMENT>>", "true" if on_active_treatment else "false")
        .replace("<<PERSPECTIVE>>", perspective if perspective in ("self", "caregiver") else "self")
    )


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    """Tolerant JSON extraction (same posture as lib/verify.py)."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    tier = str(parsed.get("tier", "")).strip().upper()
    if tier not in _VALID_TIERS:
        return None
    try:
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "tier": tier,
        "category": str(parsed.get("category", "") or "")[:80],
        "confidence": confidence,
        "rationale": str(parsed.get("rationale", "") or "")[:300],
        "rule_matched": bool(parsed.get("rule_matched", False)),
    }


@lru_cache(maxsize=1)
def _together_classifier_client():
    """Dedicated Together client: hard timeout, no retries (fail open fast)."""
    from together import Together

    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        return None
    return Together(
        api_key=api_key,
        timeout=_LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _classifier_client():
    """Provider-selected client for the classify call, or None.

    max_retries=0 on both providers: on throttling (429) the SDK would
    otherwise sleep out the Retry-After and retry (observed adding 30+
    seconds) — a throttled classifier must fall open to the deterministic
    floor immediately instead."""
    from model_registry import get_provider

    if get_provider("classifier") == "groq":
        from llm_utils import get_groq_client

        client = get_groq_client()
        return client.with_options(max_retries=0) if client else None
    return _together_classifier_client()


def _call_classifier_llm(
    message: str, on_active_treatment: bool, perspective: str
) -> Optional[Dict[str, Any]]:
    """One fast classification call. Returns parsed dict + meta, or None."""
    from model_registry import get_model

    from model_registry import get_provider

    client = _classifier_client()
    if client is None:
        return None
    model = get_model("classifier")
    call_kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": _build_system_prompt(on_active_treatment, perspective),
            },
            {"role": "user", "content": message},
        ],
        "max_tokens": _LLM_MAX_TOKENS,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    if get_provider("classifier") == "groq":
        # Groq's SDK takes a per-request timeout; Together's create() forwards
        # unknown kwargs into the API body (rejected as InvalidRequest), so
        # its timeout lives on the client constructor instead.
        call_kwargs["timeout"] = _LLM_TIMEOUT_SECONDS
    start = time.perf_counter()
    response = client.chat.completions.create(**call_kwargs)
    latency_ms = int((time.perf_counter() - start) * 1000)
    content = ""
    if response and response.choices:
        content = response.choices[0].message.content or ""
    parsed = _parse_llm_json(content)
    if parsed is None:
        return None
    parsed["model"] = model
    parsed["latency_ms"] = latency_ms
    return parsed


def classify_message(
    message: str, *, on_active_treatment: bool, perspective: str
) -> SafetyResult:
    """
    Tier one inbound message. Never raises; worst case returns the
    deterministic floor result (or NONE).
    """
    floor = deterministic_match(message)

    llm: Optional[Dict[str, Any]] = None
    if classifier_enabled():
        try:
            llm = _call_classifier_llm(message, on_active_treatment, perspective)
        except Exception as exc:  # timeout, HTTP error, SDK error — fall open
            logger.warning(f"Safety classifier LLM failed open: {type(exc).__name__}")
            llm = None

    if floor is None and llm is None:
        source = "none" if classifier_enabled() else "rules-fallback"
        return SafetyResult(source=source, **_NONE_RESULT_ARGS)

    if llm is None:
        # Floor only (outage or kill switch): deterministic result stands.
        return SafetyResult(
            tier=floor["tier"],
            category=floor["category"],
            confidence=1.0,
            rationale=f"matched rule phrase: {floor['matched_phrase']}",
            rule_matched=True,
            source="rules-fallback" if classifier_enabled() else "rules",
        )

    if floor is None:
        return SafetyResult(
            tier=llm["tier"],
            category=llm["category"],
            confidence=llm["confidence"],
            rationale=llm["rationale"],
            rule_matched=llm["rule_matched"],
            source="llm",
            model=llm["model"],
            latency_ms=llm["latency_ms"],
        )

    # Both fired: highest-precedence tier wins; floor wins ties for
    # deterministic provenance.
    merged_tier = tier_max(floor["tier"], llm["tier"])
    if merged_tier == floor["tier"]:
        winner_category = floor["category"]
        winner_rationale = f"matched rule phrase: {floor['matched_phrase']}"
    else:
        winner_category = llm["category"]
        winner_rationale = llm["rationale"]
    return SafetyResult(
        tier=merged_tier,
        category=winner_category,
        confidence=max(llm["confidence"], 0.9),
        rationale=winner_rationale,
        rule_matched=True,  # a listed rule fired regardless of which side won
        source="merged",
        model=llm["model"],
        latency_ms=llm["latency_ms"],
    )


def render_patient_line(
    tier: str,
    perspective: str,
    patient_first_name: Optional[str],
    emergency_num: Optional[str] = None,
) -> str:
    """
    The card headline, rendered SERVER-SIDE so the patient's name never
    reaches an LLM. Caregiver perspective substitutes the patient's first
    name into the tier's patient_line (name-only phrasing — no pronoun
    inference).
    """
    rules = load_safety_rules()
    tiers = rules.get("tiers") or {}
    line = str((tiers.get(tier) or {}).get("patient_line") or "")
    if not line:
        return ""
    en = (emergency_num or emergency_number()).strip()
    line = line.replace("911", en)
    if perspective == "caregiver" and patient_first_name:
        name = patient_first_name.strip()
        if name:
            replacements = {
                "This is an emergency.": f"This is an emergency for {name}.",
                "This needs a doctor now.": f"{name} needs a doctor now.",
                "This is worth a call to your care team today.":
                    f"This is worth a call to {name}'s care team today.",
                "You deserve support right now.":
                    "You deserve support right now.",
            }
            for plain, personalized in replacements.items():
                if plain in line:
                    line = line.replace(plain, personalized)
                    break
    return line
