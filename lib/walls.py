# walls.py
"""
The walls — the only gate left after the 2026-08-24 inversion.

Trajectory Brief v1.1, rule 4: the gate's ONLY job is detecting contact with
the enumerated walls — prognosis, diagnosis, and dosing/medication changes.
(The fourth wall, the crisis machinery, lives in lib/safety_classifier.py,
runs FIRST, and is frozen; it is deliberately not represented here.)
Everything else gets a real answer: "off-topic" is not a wall, because food,
work, kids, and money are on-topic when cancer lives inside a whole life.

Rule 3 (never a naked refusal): every limited answer makes the same
three-part move — answer the answerable part, name the limit in one plain
sentence, route to the patient's own care team. The limit sentences below
are FIXED TEMPLATE copy, not suggestions to the model:

  * A DIRECT personal-prognosis ask ("How long do I have?") short-circuits
    to the canned response below (mockup screen 12; its em dash became a
    period because the no-em-dash rule is enforced in code at every
    patient-facing exit, which is what §2 requires of the copy anyway).
  * Every other wall contact flows to the LLM with wall_prompt_block()
    appended to the prompt, and enforce_wall() guarantees the limit
    sentence in code afterwards — a prompt is a request, the append is
    the guarantee.

Detection is deterministic (compiled regexes), so it works identically in
production, the eval harness (wall_accuracy metric, dry mode included), and
tests. Precision over recall: a missed indirect phrasing still hits the
wall rules in chat_base.md; a false positive would bolt a medication
sentence onto a diet answer. Tune patterns against the refusal log.

All copy here is patient-facing: sixth-grade words, no em dashes, none of
the forbidden directive phrases ("you should" ...), and it does not need
the app name, so nothing interpolates branding.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

WALL_PROGNOSIS = "prognosis"
WALL_DIAGNOSIS = "diagnosis"
WALL_DOSING = "dosing"

WALL_TYPES = (WALL_PROGNOSIS, WALL_DIAGNOSIS, WALL_DOSING)


def _compile(patterns):
    return [(label, re.compile(rx)) for label, rx in patterns]


# Clause terminator for anchored patterns, and the character class for
# same-clause windows. Windows must never chain across sentence boundaries
# OR line breaks: chat messages are often unpunctuated and multi-line, so a
# bare [^.?!] quietly bridges unrelated lines.
_END = r"\s*(?:$|[?.!,])"
_IN_CLAUSE = r"[^.?!\n]"

# --- Direct personal-prognosis asks → the canned screen-12 response. ---------
# These are the phrasings where there is no answerable part: the question IS
# the prediction. Population-statistics proxies ("how long do people like me
# live") count — the canned response's first doctor question is literally the
# honest version of that ask.
#
# PRECISION RULES (2026-08-24 review): "how long do I have" is anchored to
# the naked ask — "how long do I have to wait for results" is logistics and
# must never see this card. "make it" / "my chances" are likewise anchored so
# "will I make it to work" and "what are my chances of getting into the
# trial" stay ordinary questions.
_PROGNOSIS_DIRECT = _compile([
    ("how_long_do_i_have",
     r"\bhow (?:long|much time) do i have(?: left| to live)?" + _END),
    ("how_much_longer_do_i_have",
     r"\bhow much longer do i have(?: left| to live)?" + _END),
    ("how_long_until_death", r"\bhow long (?:until|before) (?:i die|death)\b"),
    ("am_i_dying", r"\bam i dying\b"),
    ("am_i_going_to_die", r"\bam i (?:going to|gonna) die\b"),
    ("will_i_die", r"\bwill i die\b"),
    ("will_i_survive", r"\bwill i (?:survive|beat this)\b"),
    ("will_i_make_it", r"\bwill i make it(?: through this)?" + _END),
    ("am_i_going_to_survive",
     r"\bam i (?:going to|gonna) (?:survive|beat this)\b"),
    ("am_i_gonna_make_it",
     r"\bam i (?:going to|gonna) make it(?: through this)?" + _END),
    ("what_are_my_chances",
     r"\bwhat are my (?:chances|odds)(?: here| really| honestly| doc| doctor)?" + _END),
    ("chances_of_surviving",
     r"\bmy (?:chances|odds) of (?:survival|surviving|making it|beating|being cured|recovery)\b"),
    ("whats_my_prognosis", r"\bwhat(?:'s|s| is) my prognosis\b"),
    ("my_life_expectancy", r"\bmy life expectancy\b"),
    ("will_this_kill_me", r"\b(?:will|is) (?:this|it) (?:going to )?kill me\b"),
    ("how_long_do_people_live",
     r"\bhow long do (?:people|patients)" + _IN_CLAUSE + r"{0,40}\blive\b"),
])

# --- Indirect prognosis territory → LLM path with the wall rule. -------------
# Deliberately narrow: "stage" and "spread" are NOT here — "what does stage 3
# mean" is education, not a wall. Survival statistics vocabulary is.
_PROGNOSIS_INDIRECT = _compile([
    ("survival_rate", r"\bsurvival rates?\b"),
    ("life_expectancy", r"\blife expectancy\b"),
    ("prognosis", r"\bprognosis\b"),
    ("terminal", r"\bterminal\b"),
    ("cure_rate", r"\bcure rates?\b"),
    ("five_year_survival", r"\b(?:5|five)[- ]year survival\b"),
    ("chances_of_surviving",
     r"\bchances? of (?:survival|surviving|recurrence|a cure|being cured)\b"),
    ("odds_of_beating", r"\bodds of (?:beating|surviving)\b"),
])

# --- Asking Sage to conclude what they have. ---------------------------------
# The wall is CONCLUDING a diagnosis (or remission, or recurrence) for this
# person. Explaining what a test or term means stays fully answerable, which
# is why "is it cancer" is clause-anchored: "Is this cancer hereditary?" is
# an education question from someone with a known diagnosis, not a wall.
_CANCER_NOUNS = r"(?:cancer|carcinoma|lymphoma|leukemia|melanoma|sarcoma|myeloma)"
_DIAGNOSIS = _compile([
    ("do_i_have",
     r"\bdo i have (?:\w+ )?" + _CANCER_NOUNS
     + r"\b|\bdo i have (?:a tumor|a recurrence)\b"),
    ("is_it_cancer",
     r"\bis (?:this|it|that) (?:" + _CANCER_NOUNS + r"|a tumor|malignant)" + _END),
    ("could_it_be_cancer",
     r"\bcould (?:this|it|that) be (?:" + _CANCER_NOUNS + r"|a tumor|malignant)" + _END),
    ("diagnose_me",
     r"\b(?:can you |could you |please )?diagnose me\b|\bcan you diagnose\b"),
    ("what_do_i_have", r"\bwhat do i have" + _END),
    ("is_my_cancer_back",
     r"\bis (?:my|the) cancer (?:back|gone|spreading|growing|worse)\b"),
    ("has_it_spread", r"\bhas (?:my|the) cancer spread\b|\bhas it spread\b"),
    ("does_this_mean_i_have", r"\bdoes (?:this|that) mean i have\b"),
    ("am_i_in_remission", r"\bam i in remission\b"),
    ("is_this_lump",
     r"\bis (?:this|my|the) (?:lump|mole|spot|bump|swelling)\b(?:"
     + _IN_CLAUSE + r"{0,30}\b(?:cancer|bad|serious|normal|dangerous|malignant|something)\b|"
     + _END + r")"),
])

# --- Medication and dose changes. --------------------------------------------
# Verb + medication-object within one clause, plus a few high-signal bare
# phrases. "Should I change my diet" must NOT land here, which is why the
# change-verbs require a medication word nearby. Radiation and immunotherapy
# count as treatment objects (review 2026-08-24: two primary modalities were
# missing). Known accepted trade-off: "forgot to take my <anything>" walls a
# few non-medication objects; recall on missed doses is worth it.
_MEDICATION_WORDS = (
    r"(?:meds?|medications?|medicines?|pills?|tablets?|doses?|dosage|"
    r"prescriptions?)"
)
_TREATMENT_NOUNS = r"(?:treatments?|chemo(?:therapy)?|infusions?|radiation|immunotherapy)"
_DOSING = _compile([
    ("stop_taking", r"\b(?:can|should|could) i (?:stop|quit|keep) taking\b"),
    ("change_my_medication",
     r"\b(?:can|should|could|do) i (?:stop|skip|quit|pause|double|halve|"
     r"increase|decrease|lower|reduce|change|adjust)\b" + _IN_CLAUSE + r"{0,40}\b"
     + _MEDICATION_WORDS + r"\b"),
    ("change_my_treatment",
     r"\b(?:can|should|could|do) i (?:stop|skip|quit|pause|delay) "
     r"(?:my |the )?" + _TREATMENT_NOUNS + r"\b"),
    ("missed_dose",
     r"\b(?:missed|forgot|skipped) (?:a|my|the|one|last|this)\b"
     + _IN_CLAUSE + r"{0,20}\b(?:dose|pill|tablet|infusion)s?\b"),
    ("forgot_to_take", r"\bforgot to take my\b"),
    ("double_dose", r"\b(?:double|extra|half) (?:the |my |a )?(?:dose|pill|tablet)\b"),
    ("wean_off",
     r"\bwean (?:myself |me )?off\b" + _IN_CLAUSE + r"{0,25}\b"
     r"(?:" + _MEDICATION_WORDS[3:-1] + r"|" + _TREATMENT_NOUNS[3:-1] + r")\b"),
    ("stop_my_treatment",
     r"\bstop (?:my|the) (?:" + _TREATMENT_NOUNS[3:-1] + r"|meds?|medications?|pills?)\b"),
])


def detect_wall(message: str) -> Optional[Dict[str, Any]]:
    """
    Return {"type", "direct", "matched"} for the first wall the message
    touches, or None. Precedence: direct prognosis (canned path) first,
    then dosing (the most action-risky LLM-path wall), then diagnosis,
    then indirect prognosis.

    Runs AFTER the safety classifier's T1/T2/MH short-circuit — crisis
    always outranks a wall, and this function must never be consulted
    before it.
    """
    if not message:
        return None
    # iOS smart punctuation types U+2019 by default, and mobile is THE
    # product — "What's my prognosis?" must match either way.
    q = message.lower().replace("’", "'")
    for label, rx in _PROGNOSIS_DIRECT:
        if rx.search(q):
            return {"type": WALL_PROGNOSIS, "direct": True, "matched": label}
    for wall_type, patterns in ((WALL_DOSING, _DOSING),
                                (WALL_DIAGNOSIS, _DIAGNOSIS),
                                (WALL_PROGNOSIS, _PROGNOSIS_INDIRECT)):
        for label, rx in patterns:
            if rx.search(q):
                return {"type": wall_type, "direct": False, "matched": label}
    return None


# =============================================================================
# The fixed template copy (rule 3: fixed template, not improvisation)
# =============================================================================

# Each limit block is [limit sentence] + [route sentence]. The marker below is
# the distinctive core enforce_wall() checks for; every change here must keep
# the marker inside its sentence, and tests/test_walls.py pins that.
WALL_LIMIT_SENTENCES: Dict[str, str] = {
    WALL_PROGNOSIS: (
        "I can't predict what will happen for you, and I won't guess. "
        "Your oncologist can talk about this honestly, because they know "
        "your whole picture."
    ),
    WALL_DIAGNOSIS: (
        "I can't tell you what this is, and I won't guess. "
        "Finding out takes an exam and tests, and your care team is the "
        "right place to start."
    ),
    WALL_DOSING: (
        # Deliberately does NOT rank itself ("the safest next step"): the
        # answer may also carry a same-day or 911 escalation, and this
        # sentence must never read as softening that.
        "I can't tell you to change any medicine, and I won't guess about "
        "doses. Your care team sets your doses because they know your whole "
        "picture, and they can tell you exactly what to do next."
    ),
}

_WALL_MARKERS: Dict[str, str] = {
    WALL_PROGNOSIS: "predict what will happen",
    WALL_DIAGNOSIS: "tell you what this is",
    WALL_DOSING: "change any medicine",
}

# The three questions from mockup screen 12 ("Ways to ask" card). They also
# ship in the wall response metadata so a future dealt-card UI can render
# them with a save-for-visit action without re-parsing the answer text.
PROGNOSIS_DOCTOR_QUESTIONS: List[str] = [
    "What does this usually mean for people in my situation?",
    "What are we aiming for with this treatment?",
    "What would change the plan?",
]


def render_prognosis_wall_response() -> str:
    """The canned answer for a direct personal-prognosis ask (screen 12)."""
    questions = "\n".join(f"- {q}" for q in PROGNOSIS_DOCTOR_QUESTIONS)
    return (
        "I can't answer that, and I won't guess. No one can know it from "
        "the outside. Your oncologist can talk about it honestly, because "
        "they know your whole picture. Let's make sure you get a real "
        "answer from them.\n\n"
        "Questions that tend to get clear, honest answers when you ask "
        "your care team:\n" + questions
    )


_WALL_TOPIC_BANS: Dict[str, str] = {
    WALL_PROGNOSIS: (
        "Never state a number, timeframe, percentage, statistic, or "
        "prediction about this person's future course. Not even a range, "
        "and not even one from the guidelines. This overrides the "
        "completeness rules and any instruction to be honest about "
        "prognosis."
    ),
    WALL_DIAGNOSIS: (
        "Never say what their symptom, test result, or finding is or is "
        "not. Never rank how likely the possibilities are for them. "
        "Explaining what a test or a term means in general is fine."
    ),
    WALL_DOSING: (
        "Never tell them to take more, less, none, or a different schedule "
        "of any medicine. Never confirm that a change or a skipped dose is "
        "safe. The one universal caution you may give: not to take extra "
        "doses to catch up before speaking with their care team. Explaining "
        "what a medicine does in general is fine."
    ),
}


def wall_prompt_block(wall_type: str) -> str:
    """
    The instruction block appended to the assembled prompt when a wall is
    touched. Appended LAST deliberately: the instruction nearest the answer
    wins, and this one has to beat the completeness rules and any per-cancer
    overlay language.
    """
    limit = WALL_LIMIT_SENTENCES[wall_type]
    ban = _WALL_TOPIC_BANS[wall_type]
    return (
        f"WALL RULE ({wall_type.upper()}). THIS OVERRIDES EVERY OTHER "
        "INSTRUCTION ON THIS TOPIC:\n"
        "This question touches a wall. Make exactly this three-part move, "
        "in this order:\n"
        "1. Answer the part you CAN answer with general information from "
        "the guidelines: what a term means, what usually helps, what to "
        "watch for, what to expect at a visit. If nothing is answerable, "
        "skip this part.\n"
        f'2. Include these exact sentences, word for word: "{limit}"\n'
        "3. Close warmly. If it fits, offer to help them put the question "
        "into words for their care team.\n"
        f"{ban}\n"
        "Do not apologize more than once and do not add any other limits. "
        "Keep the whole answer short and plain."
    )


def enforce_wall(answer: str, wall_type: str) -> Tuple[str, bool]:
    """
    The code guarantee behind wall_prompt_block's request: if the model's
    answer does not carry the wall's fixed limit sentence (detected by its
    distinctive core, case-insensitive), append the full limit block as a
    closing paragraph. Returns (answer, appended). Idempotent — the append
    itself contains the marker.

    Runs after extract_followups and before soften_tone/enforce_voice; the
    template contains no forbidden phrases and no em dashes, so the filters
    pass it through untouched.
    """
    if not answer or wall_type not in _WALL_MARKERS:
        return answer, False
    if _WALL_MARKERS[wall_type].lower() in answer.lower():
        return answer, False
    return answer.rstrip() + "\n\n" + WALL_LIMIT_SENTENCES[wall_type], True
