# question_policy.py
"""
Coverage + the "getting to know you" conversation policy.

compute_coverage()      what we know vs. don't, importance-weighted (VOI-lite)
select_next_question()  at most ONE gentle, register-matched question per
                        eligible turn — never on urgent/emotional turns, never
                        re-asking something known or recently asked
advance_lifecycle_stage()  the monotonic stage ladder:
    getting_to_know_you -> understanding_treatment -> connected -> trial_ready

The policy is pure Python (no LLM, no I/O): the route computes a directive and
hands it to assemble_prompt, which renders it as an instruction block (and
drops it itself when its own urgency detection fires).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("question_policy")

LIFECYCLE_STAGES = (
    "getting_to_know_you",
    "understanding_treatment",
    "connected",
    "trial_ready",
)

LIFECYCLE_LABELS = {
    "getting_to_know_you": "Getting to know you",
    "understanding_treatment": "Understanding your treatment",
    "connected": "Connecting the dots",
    "trial_ready": "Trial ready",
}

# Ask at most one question every N turns.
QUESTION_TURN_COOLDOWN = 3
# Don't re-ask a topic within this many days.
TOPIC_COOLDOWN_DAYS = 7
ASKED_LOG_CAP = 30

# Coverage fields: (topic, importance, is-known predicate inputs). Importance
# is stage-aware where noted in compute_coverage.
_BASE_IMPORTANCE = {
    "site": 0.9,
    "stage": 0.9,
    "biomarkers": 0.85,     # boosted for stage III/IV, damped when stage unknown
    "treatments": 0.7,
    "zip_code": 0.65,       # what trial matching blocks on
    "age": 0.6,
    "sex": 0.55,
    "histology": 0.5,
    "symptoms_baseline": 0.45,
    "ecog": 0.4,
}

# Register-matched phrasings. Directive text only — NO patient values, so the
# PII-guard payload is unchanged by the question block.
TOPIC_DIRECTIVES: Dict[str, Dict[str, str]] = {
    "site": {
        "plain": "which type of cancer they are dealing with",
        "technical": "their primary diagnosis (cancer site)",
    },
    "stage": {
        "plain": "whether their doctor has told them what stage the cancer is",
        "technical": "their current stage (I-IV) if staging is complete",
    },
    "biomarkers": {
        "plain": "whether their doctor has mentioned any special test results about the tumor (sometimes called biomarker or genetic testing)",
        "technical": "whether biomarker results are back (e.g. KRAS/NRAS/BRAF, MSI/MMR, HER2)",
    },
    "treatments": {
        "plain": "whether they have started any treatment yet, and what it is",
        "technical": "their current regimen and treatment line",
    },
    "zip_code": {
        "plain": "their ZIP code, so answers about nearby options (like clinical trials) can be location-aware",
        "technical": "their ZIP code for location-aware trial matching",
    },
    "age": {
        "plain": "their age, since guidance often differs by age",
        "technical": "their age",
    },
    "sex": {
        "plain": "whether they are male or female, since some guidance differs",
        "technical": "their sex",
    },
    "histology": {
        "plain": "whether the doctor described what kind of tumor cells were found",
        "technical": "the histology from their pathology report",
    },
    "symptoms_baseline": {
        "plain": "how they have been feeling lately, and any symptoms bothering them",
        "technical": "their current symptom burden",
    },
    "ecog": {
        "plain": "how they are managing day-to-day activities",
        "technical": "their ECOG performance status",
    },
}


def _belief_known(beliefs: Dict[str, Any], path_prefix: str) -> bool:
    for path, entry in (beliefs.get("fields") or {}).items():
        if path == path_prefix or path.startswith(path_prefix + ".") or \
                (path_prefix.endswith(".") and path.startswith(path_prefix)):
            if entry.get("status") != "invalidated" and float(entry.get("confidence", 0)) >= 0.5:
                return True
    return False


def compute_coverage(profile: Dict[str, Any], cancer_slug: Optional[str] = None) -> Dict[str, Any]:
    """What we know / what's missing, importance-ranked. Pure function."""
    profile = profile or {}
    patient = profile.get("patient") or {}
    dx = profile.get("primaryDiagnosis") or {}
    beliefs = profile.get("beliefs") or {}

    biomarkers = {k: v for k, v in (dx.get("biomarkers") or {}).items() if v not in (None, "")}
    treatments = [t for t in (profile.get("treatments") or []) if isinstance(t, dict)]

    known: Dict[str, bool] = {
        "site": bool(dx.get("site")) or bool(cancer_slug) or _belief_known(beliefs, "primaryDiagnosis.site"),
        "stage": bool(dx.get("stage")) or _belief_known(beliefs, "primaryDiagnosis.stage"),
        "biomarkers": bool(biomarkers) or _belief_known(beliefs, "primaryDiagnosis.biomarkers"),
        "treatments": bool(treatments) or _belief_known(beliefs, "treatments"),
        "zip_code": bool(patient.get("zipCode")) or _belief_known(beliefs, "patient.zipCode"),
        "age": patient.get("age") not in (None, "") or _belief_known(beliefs, "patient.age"),
        "sex": bool(patient.get("sex")) or _belief_known(beliefs, "patient.sex"),
        "histology": bool(dx.get("histology")) or _belief_known(beliefs, "primaryDiagnosis.histology"),
        "symptoms_baseline": bool(profile.get("symptoms")) or _belief_known(beliefs, "symptoms"),
        "ecog": patient.get("ecog") not in (None, "") or _belief_known(beliefs, "patient.ecog"),
    }

    stage_value = str(dx.get("stage") or "")
    importance = dict(_BASE_IMPORTANCE)
    if "IV" in stage_value or "III" in stage_value:
        importance["biomarkers"] = 0.95      # drives therapy + trial options
        importance["zip_code"] = 0.8
    elif not known["stage"]:
        importance["biomarkers"] = 0.6       # stage first, then biomarkers
    if not treatments:
        importance["treatments"] = max(importance["treatments"], 0.75)

    total_weight = sum(importance.values())
    score = sum(importance[k] for k, v in known.items() if v) / total_weight if total_weight else 0.0
    missing_ranked = sorted(
        ((k, importance[k]) for k, v in known.items() if not v),
        key=lambda kv: kv[1], reverse=True,
    )

    return {
        "fields": known,
        "importance": importance,
        "score": round(score, 3),
        "missing_ranked": missing_ranked,
        "known_count": sum(1 for v in known.values() if v),
        "trial_missing_critical": [f for f in ("zip_code", "stage") if not known[f]],
    }


def advance_lifecycle_stage(profile: Dict[str, Any],
                            coverage: Dict[str, Any]) -> Tuple[str, bool]:
    """
    Monotonic stage ladder. Reads/writes the mirror in
    profile['model_state']['lifecycle_stage'] (the patient_profiles column is
    updated by the caller when this reports a change). Returns (stage, changed).
    """
    model_state = profile.setdefault("model_state", {})
    current = model_state.get("lifecycle_stage", "getting_to_know_you")
    if current not in LIFECYCLE_STAGES:
        current = "getting_to_know_you"
    known = coverage["fields"]

    target = "getting_to_know_you"
    if known["site"] and (known["stage"] or known["treatments"]):
        target = "understanding_treatment"
        if coverage["score"] >= 0.6 and known["biomarkers"] and known["treatments"]:
            target = "connected"
            helpful = sum(1 for f in ("biomarkers", "age", "sex", "treatments") if known[f])
            if not coverage["trial_missing_critical"] and helpful >= 2:
                target = "trial_ready"

    # Monotonic: never regress.
    if LIFECYCLE_STAGES.index(target) > LIFECYCLE_STAGES.index(current):
        model_state["lifecycle_stage"] = target
        return target, True
    model_state.setdefault("lifecycle_stage", current)
    return current, False


def _topic_recently_asked(model_state: Dict[str, Any], topic: str) -> bool:
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=TOPIC_COOLDOWN_DAYS)
    for entry in model_state.get("asked_questions") or []:
        if entry.get("topic") != topic:
            continue
        try:
            asked = datetime.fromisoformat(str(entry.get("asked_at", "")).rstrip("Z"))
            if asked >= cutoff:
                return True
        except ValueError:
            return True
    return False


def select_next_question(coverage: Dict[str, Any], model_state: Dict[str, Any],
                         signals: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Pick at most one topic to gently ask about this turn, or None.

    signals: {query_type, question_marks, response_length,
              has_pending_confirmations, register}
    (Urgency/crisis suppression happens downstream: assemble_prompt drops the
    directive when its own urgency detection fires, and crisis turns never
    reach prompt assembly at all.)
    """
    if signals.get("query_type") == "emotional":
        return None
    if signals.get("response_length") == "brief":
        return None
    if int(signals.get("question_marks", 0)) >= 2:      # multi-part question
        return None
    if signals.get("has_pending_confirmations"):        # chips take priority
        return None
    if int(model_state.get("turns_since_question", QUESTION_TURN_COOLDOWN)) < QUESTION_TURN_COOLDOWN:
        return None

    register = signals.get("register") or model_state.get("register") or "plain"
    register_key = "technical" if register == "technical" else "plain"

    for topic, _importance in coverage.get("missing_ranked") or []:
        if _topic_recently_asked(model_state, topic):
            continue
        directive = TOPIC_DIRECTIVES.get(topic, {}).get(register_key)
        if directive:
            return {"topic": topic, "directive": directive, "register": register_key}
    return None


def record_turn(model_state: Dict[str, Any], asked_topic: Optional[str]) -> None:
    """Bookkeeping after a turn: cooldown counter + asked-question log."""
    from patient_model import _now_iso
    if asked_topic:
        log = model_state.setdefault("asked_questions", [])
        log.insert(0, {"topic": asked_topic, "asked_at": _now_iso()})
        del log[ASKED_LOG_CAP:]
        model_state["turns_since_question"] = 0
    else:
        model_state["turns_since_question"] = int(model_state.get("turns_since_question", 0)) + 1
