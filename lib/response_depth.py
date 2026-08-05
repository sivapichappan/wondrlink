"""How much answer this person wants, inferred rather than asked.

Sage used to carry a Settings toggle: Brief, Normal, Detailed. Almost nobody
touches a setting like that, and it asks someone who was diagnosed last week to
calibrate a thing they have no basis for calibrating. So it is gone, and the
answer sizes itself to how the person is actually engaging.

THE SHAPE OF "SHORTER" MATTERS MORE THAN THE LENGTH. Owner direction: a patient
moving slowly gets a short answer that always offers more, with the follow-up
chips carrying the depth. That is the opposite of the old `brief` level, which
switched the chips OFF along with the resources row and the gentle
getting-to-know-you question. The people getting the most hand-holding would
have been the only ones with no door to walk through. `guided` is short and
keeps all three; see get_response_settings in llm_utils.

PURE. No LLM, no database, no clock beyond `now`. Mirrors question_policy.py,
which is the established pattern here for exactly this kind of decision, and it
means the whole thing is testable as a table of inputs.

EVERY DECISION IS EXPLAINABLE. `why` names the signals that fired, and rides in
debug_info, which is persisted per turn. Reading an exported run afterwards, the
question is never "why was this one short" — it says so.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("wondr-api")

GUIDED = "guided"
STANDARD = "standard"
DEEP = "deep"

# The shared list is colorectal-heavy (FOLFOX, KRAS, cetuximab) because that is
# the cancer it was written for. Supplemented rather than mutated: it is also
# read by update_register_signal, which has its own tests, and widening a shared
# constant to fix one caller is how the next person inherits a surprise.
_CROSS_CANCER_TERMS = (
    # breast
    "tamoxifen", "letrozole", "anastrozole", "exemestane", "aromatase",
    "lumpectomy", "mastectomy", "sentinel", "oncotype", "brca", "hr+", "hr-positive",
    "triple-negative", "trastuzumab", "pertuzumab", "cdk4", "endocrine therapy",
    # lung / melanoma / prostate / nhl / kidney / bladder
    "alk", "ros1", "nsclc", "sclc", "durvalumab", "osimertinib",
    "gleason", "psa", "androgen", "adt", "rituximab", "r-chop", "dlbcl", "car-t",
    "nephrectomy", "cystectomy", "bcg", "ipilimumab", "nivo",
    # cross-cutting clinical register
    "histology", "grade 3", "stage iii", "stage iv", "margins", "node-positive",
    "recurrence", "adjuvant", "cytology", "immunohistochem",
)


def _technical_terms() -> tuple:
    try:
        from patient_model import _TECHNICAL_TERMS
        return tuple(_TECHNICAL_TERMS) + _CROSS_CANCER_TERMS
    except Exception:  # noqa: BLE001
        return _CROSS_CANCER_TERMS


def _parse_ts(value: Any) -> Optional[datetime]:
    """Supabase timestamps, tolerant of the shapes it actually returns."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def choose_depth(message: str,
                 profile: Optional[Dict[str, Any]] = None,
                 history: Optional[List[Dict[str, Any]]] = None,
                 query_type: str = "general",
                 now: Optional[datetime] = None) -> Dict[str, Any]:
    """Pick guided | standard | deep for this turn.

    Four signals, each contributing a small amount to one score, so no single
    one can run away with the decision. A person who writes plainly but asks a
    long, layered question still gets a fuller answer, which is the point.

    Returns {"depth", "score", "why"}. Never raises: on anything unexpected it
    returns STANDARD, because the reviewer sandbox has a synthetic profile with
    no model_state and no history, and a brand-new patient has neither either.
    """
    try:
        return _choose_depth(message, profile or {}, history or [], query_type, now)
    except Exception:  # noqa: BLE001
        logger.exception("depth policy failed; falling back to standard")
        return {"depth": STANDARD, "score": 0.0, "why": ["policy-error"]}


def _choose_depth(message: str, profile: Dict[str, Any],
                  history: List[Dict[str, Any]], query_type: str,
                  now: Optional[datetime]) -> Dict[str, Any]:
    text = (message or "").strip()
    lowered = text.lower()
    words = len(text.split())
    score = 0.0
    why: List[str] = []

    # --- 1. how technically they write -------------------------------------
    # Density, not a raw count: "is HER2 bad?" is three words with one term and
    # should not read the same as a paragraph that happens to contain one.
    hits = sum(1 for t in _technical_terms() if t in lowered)
    if hits:
        density = hits / max(words / 12.0, 1.0)
        if density >= 1.5 or hits >= 3:
            # Weighted to outrank a single opposing signal. Someone writing
            # "HR+/HER2- invasive ductal carcinoma, grade 2, node-positive" is
            # telling you what they want more clearly than their lifecycle
            # stage is telling you otherwise.
            score += 1.25
            why.append(f"technical language ({hits} terms)")
        else:
            score += 0.5
            why.append(f"some clinical terms ({hits})")

    # A belief blended over previous turns is a better signal than one message,
    # so use it when it exists. It does not today (the writer is behind a
    # dormant flag and writes somewhere its only reader does not look), which
    # is why it is a bonus rather than the basis.
    stored = (((profile.get("beliefs") or {}).get("fields") or {})
              .get("meta.communication_register") or {}).get("value")
    if isinstance(stored, dict):
        reg = stored.get("register")
        if reg == "technical":
            score += 0.5
            why.append("writes technically over time")
        elif reg == "plain":
            score -= 0.5
            why.append("writes plainly over time")

    # --- 2. how much they asked --------------------------------------------
    if words >= 20 or text.count("?") >= 2:
        score += 1.0
        why.append("detailed or multi-part question")
    elif words <= 6:
        # Gentle. "How do I manage fatigue during treatment?" is seven words
        # and a perfectly ordinary question that deserves an ordinary answer,
        # so the penalty starts below that.
        score -= 0.5
        why.append("short question")

    # --- 3. pace of the session --------------------------------------------
    # Someone in rapid back-and-forth is actively working through it and can
    # absorb more. Someone returning after a long gap is not mid-thought.
    now = now or datetime.now(timezone.utc)
    stamps = [t for t in (_parse_ts(h.get("created_at")) for h in history) if t]
    if len(history) >= 4:
        score += 0.5
        why.append(f"{len(history)} turns deep")
    if stamps:
        last = stamps[-1]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        gap_minutes = (now - last).total_seconds() / 60.0
        if gap_minutes <= 3:
            score += 0.5
            why.append("rapid back and forth")
        elif gap_minutes >= 240:
            score -= 0.5
            why.append("returning after a break")
    elif not history:
        # First message of a thread. Nothing earned yet either way.
        why.append("first message")

    # --- 4. where they are in the journey ----------------------------------
    # Only when it is actually KNOWN. Defaulting an absent stage to
    # "getting_to_know_you" would treat every reviewer-sandbox turn and every
    # profile-less caller as newly diagnosed, which quietly shortens answers
    # for people we simply know nothing about.
    stage = (profile.get("model_state") or {}).get("lifecycle_stage")
    if stage == "getting_to_know_you":
        score -= 0.75
        why.append("newly diagnosed")
    elif stage in ("connected", "trial_ready"):
        score += 0.5
        why.append(f"further along ({stage})")

    # --- decide -------------------------------------------------------------
    # Trial questions are inherently detailed and eligibility is unforgiving of
    # a summary, so they never drop to guided.
    if query_type == "clinical_trial" and score < 0.0:
        score = 0.0
        why.append("trial question, not shortened")

    if score <= -0.75:
        depth = GUIDED
    elif score >= 1.5:
        depth = DEEP
    else:
        depth = STANDARD

    return {"depth": depth, "score": round(score, 2), "why": why}
