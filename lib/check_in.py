# check_in.py
"""
Check-ins as engine-chosen questions (Trajectory Brief v1.1, change 4).

Before: six standalone questionnaires — "Depression (PHQ-9)", and a result
that read "LATEST PHQ-9: Moderately severe." After: two or three plain
questions, chosen from what this person is actually being treated with,
asked in the conversation.

The named, accepted cost of that trade is on the record in the brief: no
validated scores and no severity trends remain, and the Lynch-syndrome
screen (PREMM5) dies with the rest. What is gained is a check-in a tired
person will actually answer.

Design rules this file enforces:
  * ASK-BUDGET (rule 6): at most 3 questions, and only questions tied to
    this patient's own treatment. A general question is a fallback, never
    a filler to pad the count.
  * ESCAPE HATCH (rule 6): "Not now" is always available, and the cooldown
    treats it as an answer — declining is a settled question, not a
    prompt to ask again tomorrow.
  * PREDICTIONS STAY IN THE BACK (rule 5): the regimen match decides WHICH
    question is asked. Nothing about the reasoning is ever said to the
    patient, and no question implies what will happen to them.
  * The question text is DATA (config/check_in/questions.json), reviewable
    by a clinician without touching code, exactly like config/safety/.

Self-harm note: PHQ-9's question 9 used to be the app's structured
self-harm detector. It dies with the questionnaire. That detection does
not disappear — every check-in answer is a normal chat turn, so it passes
through the frozen safety layer (MH tier) and the client-side crisis
guardrail like any other message. This is a deliberate relocation, and it
is why check-in answers must keep flowing through /api/chat rather than
being written straight to storage.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("check_in")

_BANK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "check_in", "questions.json",
)

# How long a question rests after it is asked, answered or declined. A week
# matches the treatment rhythm most regimens run on.
COOLDOWN_DAYS = 7
# Rule 6: "at most 2-3 questions per check-in".
MAX_QUESTIONS = 3
# How often the whole check-in may be offered at all.
CHECK_IN_INTERVAL_DAYS = 7

_MATCH_ANY = "*"

_bank_cache: Optional[Dict[str, Any]] = None


def load_bank() -> Dict[str, Any]:
    """Read the question bank. Cached; a bad file degrades to no check-in
    rather than to a broken one."""
    global _bank_cache
    if _bank_cache is not None:
        return _bank_cache
    try:
        with open(_BANK_PATH, "r", encoding="utf-8") as fh:
            _bank_cache = json.load(fh)
    except Exception:
        logger.exception("check-in question bank failed to load")
        _bank_cache = {"questions": []}
    return _bank_cache


def _treatment_terms(profile: Dict[str, Any]) -> List[str]:
    """Every lowercase term describing what this person is being treated
    with: regimen, category and drug names off ACTIVE treatments only."""
    terms: List[str] = []
    for t in (profile.get("treatments") or []):
        if not isinstance(t, dict):
            continue
        if t.get("status") not in (None, "", "active", "ongoing"):
            continue
        for key in ("regimen", "category", "name", "drug"):
            val = t.get(key)
            if isinstance(val, str) and val.strip():
                terms.append(val.strip().lower())
    return terms


def _matches(question: Dict[str, Any], terms: List[str]) -> bool:
    match = [str(m).lower() for m in (question.get("match") or [])]
    if _MATCH_ANY in match:
        return True
    return any(m in term for m in match for term in terms)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").split("+")[0])
    except Exception:
        return None


def _on_cooldown(question_id: str, log: List[Dict[str, Any]], now: datetime) -> bool:
    for entry in log:
        if not isinstance(entry, dict) or entry.get("id") != question_id:
            continue
        when = _parse_iso(entry.get("at"))
        if when and now - when < timedelta(days=COOLDOWN_DAYS):
            return True
    return False


def select_check_in(profile: Dict[str, Any],
                    model_state: Optional[Dict[str, Any]] = None,
                    now: Optional[datetime] = None,
                    perspective: str = "self") -> List[Dict[str, Any]]:
    """
    Pick at most MAX_QUESTIONS plain questions for this patient, or [].

    Treatment-specific questions come first and in bank order; a general
    question fills the remainder ONLY when fewer than two treatment-tied
    questions are available, so the check-in never becomes generic padding.
    Returns patient-ready dicts: id, topic, text, chips.

    `perspective` picks the written caregiver variant. A caregiver account is
    held by one person and is ABOUT another, so "any tingling in YOUR
    fingers" asks the daughter about her own hands. The variants are written
    out in the bank rather than substituted at runtime: these sentences have
    no mechanical rewrite that stays grammatical.
    """
    profile = profile or {}
    state = model_state or {}
    now = now or datetime.utcnow()
    log = [e for e in (state.get("check_in_log") or []) if isinstance(e, dict)]

    bank = load_bank().get("questions") or []
    terms = _treatment_terms(profile)

    specific: List[Dict[str, Any]] = []
    general: List[Dict[str, Any]] = []
    for q in bank:
        if not isinstance(q, dict) or not q.get("id") or not q.get("text"):
            continue
        if _on_cooldown(str(q["id"]), log, now):
            continue
        match = [str(m).lower() for m in (q.get("match") or [])]
        if _MATCH_ANY in match:
            general.append(q)
        elif _matches(q, terms):
            specific.append(q)

    chosen = specific[:MAX_QUESTIONS]
    if len(chosen) < 2:
        chosen += general[: MAX_QUESTIONS - len(chosen)]

    caregiver = str(perspective).lower() == "caregiver"
    return [
        {
            "id": q["id"],
            "topic": q.get("topic") or q["id"],
            "text": (q.get("text_caregiver") or q["text"]) if caregiver else q["text"],
            "chips": list(q.get("chips") or []),
        }
        for q in chosen[:MAX_QUESTIONS]
    ]


def check_in_due(model_state: Optional[Dict[str, Any]] = None,
                 now: Optional[datetime] = None) -> bool:
    """Whether the whole check-in may be offered at all right now."""
    state = model_state or {}
    now = now or datetime.utcnow()
    last = _parse_iso(state.get("last_check_in_at"))
    if last is None:
        return True
    return now - last >= timedelta(days=CHECK_IN_INTERVAL_DAYS)


def record_check_in(model_state: Dict[str, Any],
                    question_ids: List[str],
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Put the asked/answered/declined questions on cooldown and stamp the
    check-in. Mutates and returns model_state, matching question_policy's
    record_turn convention.

    Declining counts: "Not now" has to mean it, or the escape hatch is a
    snooze button that asks again tomorrow.
    """
    now = now or datetime.utcnow()
    stamp = now.isoformat()
    log = model_state.setdefault("check_in_log", [])
    for qid in question_ids:
        if not qid:
            continue
        log.insert(0, {"id": str(qid), "at": stamp})
    # Keep the log bounded; anything older than the cooldown is dead weight.
    del log[50:]
    model_state["last_check_in_at"] = stamp
    return model_state


def follow_up_for(question_id: str, perspective: str = "self") -> Optional[str]:
    """Sage's plain acknowledgement for a question, from the bank."""
    caregiver = str(perspective).lower() == "caregiver"
    for q in load_bank().get("questions") or []:
        if isinstance(q, dict) and q.get("id") == question_id:
            follow = (q.get("follow_caregiver") or q.get("follow")) if caregiver else q.get("follow")
            return follow if isinstance(follow, str) and follow else None
    return None
