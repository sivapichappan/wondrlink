"""
Hero card data assembly (Phase C.1 of investor-grade UI pass).

Produces the personalized welcome card content displayed at the top of the
chat on app load. Powered by the existing patient_profiles.raw_profile JSON
plus the visit_recaps[] entries written by the Visit Companion feature.

No LLM call here — fast, deterministic, rule-based. Suggestions are pulled
from a small profile-phase rubric so the hero loads in <100ms.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional


# --- Treatment phase classification --------------------------------------

def _parse_iso_date(value: str) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.split("T")[0])
    except Exception:
        return None


def compute_days_into_treatment(profile: Dict[str, Any]) -> Optional[int]:
    """Days since the active treatment's startDate. None if unknown."""
    treatments = (profile or {}).get("treatments") or []
    if not isinstance(treatments, list):
        return None
    for t in treatments:
        if not isinstance(t, dict):
            continue
        if t.get("status") != "active":
            continue
        start = _parse_iso_date(t.get("startDate", ""))
        if not start:
            continue
        delta = datetime.utcnow() - start
        days = delta.days
        return max(0, days)
    return None


def detect_treatment_phase(profile: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    """
    Categorize the patient into a coarse phase used to pick suggested questions.
    Phases:
      - 'early_chemo'           : on an active chemo regimen, days_into < 28
      - 'mid_chemo'             : on an active chemo regimen, 28 <= days_into < 120
      - 'late_chemo'            : on an active chemo regimen, days_into >= 120
      - 'surveillance'          : surgical history exists, no active treatment
      - 'newly_diagnosed'       : diagnosis exists but no treatment yet
      - 'general'               : fallback
    """
    days = compute_days_into_treatment(profile)
    regimen = (ctx or {}).get("current_regimen") or ""
    has_active_chemo = bool(regimen)
    has_surgery = bool((profile or {}).get("surgicalHistory"))
    has_dx = bool((ctx or {}).get("cancer_type"))

    if has_active_chemo:
        if days is None:
            return "mid_chemo"
        if days < 28:
            return "early_chemo"
        if days < 120:
            return "mid_chemo"
        return "late_chemo"
    if has_surgery and not has_active_chemo:
        return "surveillance"
    if has_dx:
        return "newly_diagnosed"
    return "general"


# --- Suggested starter questions per phase --------------------------------

_PHASE_SUGGESTIONS = {
    "early_chemo": [
        "What side effects from cycle 1 should I watch for?",
        "When does fatigue typically peak in this regimen?",
        "Help me prepare for my next visit",
    ],
    "mid_chemo": [
        "How will we know if my treatment is working?",
        "Are there ways to manage neuropathy as it builds up?",
        "Help me prepare for my next visit",
    ],
    "late_chemo": [
        "What questions should I bring to my next scan?",
        "What does life after treatment typically look like?",
        "Help me prepare for my next visit",
    ],
    "surveillance": [
        "When is my next colonoscopy due?",
        "What signs of recurrence should I watch for?",
        "Help me prepare for my next visit",
    ],
    "newly_diagnosed": [
        "Walk me through what stage {stage} means for my care",
        "What treatment options should I discuss with my team?",
        "Help me prepare for my first treatment visit",
    ],
    "general": [
        "What questions should I ask my oncology team?",
        "How can I prepare for my next appointment?",
        "Help me prepare for my next visit",
    ],
}


def suggest_starter_questions(profile: Dict[str, Any], ctx: Dict[str, Any]) -> List[str]:
    """Return three suggested questions based on the patient's treatment phase."""
    phase = detect_treatment_phase(profile, ctx)
    raw = _PHASE_SUGGESTIONS.get(phase, _PHASE_SUGGESTIONS["general"])
    stage = (ctx or {}).get("stage") or "your stage"
    return [q.replace("{stage}", str(stage)) for q in raw]


# --- Last visit summary ---------------------------------------------------

def format_visit_summary(recap_entry: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Compact summary of the most-recent visit recap for the hero pill.

    Returns:
        {
          'when': '2026-04-22',
          'when_pretty': 'Apr 22',
          'pending_followups': int,
          'changed_treatment': bool,
        }
        or None if no recap available.
    """
    if not recap_entry or not isinstance(recap_entry, dict):
        return None
    timestamp = recap_entry.get("timestamp") or ""
    when_dt = _parse_iso_date(timestamp)
    when_pretty = when_dt.strftime("%b %-d") if when_dt else "recently"
    recap = recap_entry.get("recap") or {}
    pending = 0
    if isinstance(recap, dict):
        pending += len(recap.get("action_items") or [])
        pending += len(recap.get("follow_up_questions") or [])
    changed = bool((recap or {}).get("treatment_changes"))
    return {
        "when": (timestamp or "").split("T")[0] if timestamp else None,
        "when_pretty": when_pretty,
        "pending_followups": pending,
        "changed_treatment": changed,
    }


# --- Pretty descriptor of treatment phase --------------------------------

def describe_phase(profile: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    """
    Human-readable description of where the patient is in their journey.
    Used as the subtitle line under the welcome greeting.

    Examples:
      "You're 14 days into FOLFOX + Bevacizumab, cycle 2."
      "8 days post-surgery — beginning surveillance."
      "Newly diagnosed — stage IIIB, sigmoid colon adenocarcinoma."
    """
    days = compute_days_into_treatment(profile)
    regimen = (ctx or {}).get("current_regimen") or ""
    cycle = (ctx or {}).get("current_cycle_number")
    phase = detect_treatment_phase(profile, ctx)

    if phase in ("early_chemo", "mid_chemo", "late_chemo") and regimen:
        cycle_clause = f", cycle {cycle}" if cycle else ""
        days_clause = f"{days} day{'s' if days != 1 else ''} into " if isinstance(days, int) and days > 0 else "on "
        return f"You're {days_clause}{regimen}{cycle_clause}."
    if phase == "surveillance":
        # Days since surgery (if available)
        surgeries = (profile or {}).get("surgicalHistory") or []
        s_days = None
        if isinstance(surgeries, list) and surgeries:
            s = surgeries[-1]
            if isinstance(s, dict):
                start = _parse_iso_date(s.get("date", ""))
                if start:
                    s_days = max(0, (datetime.utcnow() - start).days)
        if s_days is not None:
            return f"{s_days} days post-surgery — surveillance phase."
        return "You're in the surveillance phase."
    if phase == "newly_diagnosed":
        stage = (ctx or {}).get("stage") or ""
        cancer = (ctx or {}).get("cancer_type") or "colorectal cancer"
        stage_clause = f"stage {stage}, " if stage else ""
        return f"Newly diagnosed — {stage_clause}{cancer}."
    return "Welcome back."
