# safety_rules.py
"""
Sage safety rules: loader + deterministic tier matching.

The supervisor's red-flag rule set ships as DATA
(`config/safety/sage-safety-rules-v0.9.json`, pristine — never hand-edited)
plus a repo-owned extensions file in the same schema
(`sage-safety-rules-local-extensions.json`, the typed-phrase triggers migrated
from the legacy lib/confidence.py crisis list). Both feed one matcher.

Tiers (UI treatment decided by the caller):
  T1  emergency        escalation card leading with Call 911, no chat reply
  T2  urgent           escalation card leading with "Call your care team right away"
  T3  same_day         soft banner above the normal chat reply
  MH  mental-health    compassionate 988 response, never the medical card
  NONE                 proceed to normal chat

`deterministic_match()` is the zero-latency FLOOR: pure substring scanning,
no network, always available. The LLM judgment layer (lib/safety_classifier.py)
can only raise the tier, never lower it.

Tier precedence: T1 outranks MH (an active physical emergency needs 911 first;
the card appends 988 when self-harm is also present). MH outranks T2/T3 — a
self-harm signal is never downgraded to a medical banner.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_SAFETY_DIR = Path(__file__).resolve().parent.parent / "config" / "safety"
_BASE_FILE = _SAFETY_DIR / "sage-safety-rules-v0.9.json"
_EXTENSIONS_FILE = _SAFETY_DIR / "sage-safety-rules-local-extensions.json"

# Rank encodes escalation precedence, not raw severity ordering: T1 > MH > T2 > T3.
TIER_RANK: Dict[str, int] = {"NONE": 0, "T3": 1, "T2": 2, "MH": 3, "T1": 4}

VALID_TIERS = ("T1", "T2", "T3", "MH", "NONE")

# Window (chars, each side) for co_modifier proximity checks — matches the
# legacy despair-co-modifier behavior.
_CO_MODIFIER_WINDOW = 60


def emergency_number() -> str:
    """Emergency number as config (launching outside the US = env change)."""
    return os.getenv("EMERGENCY_NUMBER", "911").strip() or "911"


@lru_cache(maxsize=1)
def load_safety_rules() -> Dict[str, Any]:
    """Merged rule set: base file (tiers/contract/fallback) + extension rules."""
    with _BASE_FILE.open() as f:
        base = json.load(f)
    merged = dict(base)
    merged["rules"] = list(base.get("rules") or [])
    try:
        with _EXTENSIONS_FILE.open() as f:
            ext = json.load(f)
        merged["rules"].extend(ext.get("rules") or [])
        merged["_extensions_version"] = ext.get("version", "")
    except FileNotFoundError:
        merged["_extensions_version"] = ""
    return merged


def rules_version() -> str:
    """Combined version string for audit rows and eval report headers."""
    rules = load_safety_rules()
    ext = rules.get("_extensions_version") or ""
    base = rules.get("version", "?")
    return f"{base}+{ext}" if ext else str(base)


def tier_max(a: str, b: str) -> str:
    """The more escalated of two tiers (see TIER_RANK for MH/T1 precedence)."""
    ra = TIER_RANK.get(a, 0)
    rb = TIER_RANK.get(b, 0)
    return a if ra >= rb else b


def deterministic_match(message: str) -> Optional[Dict[str, Any]]:
    """
    Zero-latency substring scan of every rule trigger. Returns the
    highest-precedence hit as {tier, category, matched_phrase,
    rule_matched: True} or None.

    Cancer-agnostic and independent of the LLM layer — this is the safety
    floor that survives provider outages.
    """
    if not message:
        return None
    q_lower = message.lower()
    best: Optional[Dict[str, Any]] = None
    for rule in load_safety_rules()["rules"]:
        tier = rule.get("tier")
        if tier not in TIER_RANK or tier == "NONE":
            continue
        co_modifiers: List[str] = rule.get("co_modifiers") or []
        for trigger in rule.get("triggers") or []:
            t_lower = str(trigger).lower()
            idx = q_lower.find(t_lower)
            if idx < 0:
                continue
            if co_modifiers:
                lo = max(0, idx - _CO_MODIFIER_WINDOW)
                hi = idx + len(t_lower) + _CO_MODIFIER_WINDOW
                window = q_lower[lo:hi]
                if not any(m in window for m in co_modifiers):
                    continue
            hit = {
                "tier": tier,
                "category": rule.get("category", "unknown"),
                "matched_phrase": t_lower,
                "rule_matched": True,
            }
            if best is None or TIER_RANK[tier] > TIER_RANK[best["tier"]]:
                best = hit
            break  # one trigger per rule is enough; keep scanning other rules
    return best
