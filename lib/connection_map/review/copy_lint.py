"""Patient-facing copy rules (SPEC §8), and the D1 check on physician edits.

Two different jobs, deliberately kept apart:

  * lint_patient_copy() is a HARD rule. §8 says a patient-facing string failing
    these fails CI, and publication refuses an edge whose phrasing breaks them.
    Deterministic, no model involved.

  * review_edit_concerns() is the SOFT check the owner asked for (D1): when a
    physician edits wording, sanity-check it and hand back a note. It warns and
    never blocks, because a qualified clinician made the edit. It applies ONLY
    to wording and metadata. It never touches a quotation: citations are exact
    string matches, verified in the database, and no advisory check may become
    an alternative route to storing an unverified quote.

No imports from patient modules — see the package docstring.
"""

import re
from typing import Dict, List, Optional

# §8: no causal verbs. A connection is something noticed together, never
# something asserted to cause something else.
#
# Every multi-word pattern uses \s+ rather than a literal space: real copy
# contains double spaces, line breaks after a wrap, and non-breaking spaces,
# and "leads  to" is exactly as much a causal claim as "leads to". Inflections
# are listed too — "causing" and "resulting in" assert cause just as plainly as
# "causes", and an earlier version matched neither.
CAUSAL_PATTERNS = (
    (r"\bcaus(?:e|es|ed|ing)\b", "causes"),
    (r"\bcaus(?:e|es|ed|ing)\s+by\b", "caused by"),
    (r"\blead(?:s|ing)?\s+to\b", "leads to"),
    (r"\bresult(?:s|ed|ing)?\s+in\b", "results in"),
    (r"\bbecause\s+of\b", "because of"),
    (r"\bdue\s+to\b", "due to"),
    (r"\btrigger(?:s|ed|ing)?\b", "triggers"),
    (r"\bmake(?:s|ing)?\s+you\b", "makes you"),
    (r"\bbrings?\s+on\b", "brings on"),
    (r"\bgives?\s+you\b", "gives you"),
    (r"\bresponsible\s+for\b", "responsible for"),
    (r"\bstems?\s+from\b", "stems from"),
    (r"\bcomes?\s+from\b", "comes from"),
)

# §8: no numerals expressing confidence or probability. Spelled-out numbers
# count too — "nine in ten" is a probability claim in words, and §3 forbids
# rendering confidence "in any form", not merely in digits.
_NUMBER_WORD = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|"
                r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|half)")
CONFIDENCE_PATTERNS = (
    r"\b\d+\s*%",
    r"\b\d+\s*(?:in|out\s+of)\s+\d+\b",
    rf"\b{_NUMBER_WORD}\s+(?:in|out\s+of)\s+{_NUMBER_WORD}\b",
    r"\b(?:percent|percentage|probability|likelihood|confidence)\b",
    r"\bodds\b",
    r"\b(?:most|nearly all|almost all|the majority)\s+(?:people|patients|women)\b",
)

# §8 permits these framings; used only to explain a finding, never to gate.
PERMITTED_FRAMINGS = (
    "some people", "often go together", "worth mentioning to your care team",
    "notice", "seem to go together",
)

EM_DASH = "—"
EN_DASH = "–"

# Readability. §8 asks for grade 6 or below. The earlier version only counted
# sentence length and long words, which let clinician-written copy several
# grades above target pass — "Patients receiving endocrine therapy frequently
# experience arthralgia" is short, has no 13-character word, and is nowhere
# near grade 6.
#
# Flesch-Kincaid is used instead, with a deliberate two-grade margin on the
# HARD block: the formula is noisy on strings this short, and blocking a
# physician's valid wording is a worse failure than letting grade 7 through.
# Between the target and the block it produces a soft concern instead, so the
# reviewer sees it and decides.
TARGET_GRADE = 6.0
MAX_GRADE = 8.0

MAX_WORDS_PER_SENTENCE = 22
MAX_LONG_WORDS = 3
LONG_WORD_CHARS = 13


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def _syllables(word: str) -> int:
    """Rough syllable count. Approximate by design — it feeds a readability
    estimate that already carries a margin, not a hard fact."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    groups = re.findall(r"[aeiouy]+", w)
    return max(1, len(groups))


def reading_grade(text: str) -> float:
    """Flesch-Kincaid grade level. Returns 0.0 for text with no words."""
    sentences = _sentences(text)
    words = re.findall(r"[A-Za-z']+", text)
    if not words or not sentences:
        return 0.0
    syllables = sum(_syllables(w) for w in words)
    return (0.39 * (len(words) / len(sentences))
            + 11.8 * (syllables / len(words))
            - 15.59)


def lint_patient_copy(text: Optional[str]) -> List[str]:
    """Hard §8 violations. Empty list means the string is publishable."""
    problems: List[str] = []
    if text is None or not text.strip():
        return ["patient copy is empty"]

    if EM_DASH in text:
        problems.append("contains an em dash; use a period, a comma, or a new sentence")
    if EN_DASH in text:
        problems.append("contains an en dash; use a period, a comma, or a new sentence")

    lowered = text.lower()
    for pattern, label in CAUSAL_PATTERNS:
        if re.search(pattern, lowered):
            problems.append(f"contains the causal phrase '{label}'; state it as something noticed together")

    for pattern in CONFIDENCE_PATTERNS:
        if re.search(pattern, lowered):
            problems.append("expresses confidence or probability in numbers; not permitted in patient copy")

    for sentence in _sentences(text):
        words = sentence.split()
        if len(words) > MAX_WORDS_PER_SENTENCE:
            problems.append(
                f"sentence of {len(words)} words is too long for a grade 6 reading level "
                f"(limit {MAX_WORDS_PER_SENTENCE}); split it")

    long_words = [w for w in re.findall(r"[A-Za-z]+", text) if len(w) >= LONG_WORD_CHARS]
    if len(long_words) > MAX_LONG_WORDS:
        problems.append(f"too many long words for a grade 6 reading level: {sorted(set(long_words))[:5]}")

    grade = reading_grade(text)
    if grade > MAX_GRADE:
        problems.append(
            f"reads at about grade {grade:.0f}; §8 asks for grade {TARGET_GRADE:.0f} or below")

    return problems


def review_edit_concerns(
    new_text: str,
    quoted_sentences: Optional[List[str]] = None,
    previous_text: Optional[str] = None,
) -> Dict[str, object]:
    """D1: sanity-check a physician's edit. Advisory only.

    Returns {"blocking": [...], "concerns": [...]}. `blocking` carries only the
    hard §8 rules, which apply to anyone. `concerns` is the soft half: a note
    to show the physician, who decides. Nothing here can reject an edit on
    clinical grounds; this is not an authority on medicine.
    """
    blocking = lint_patient_copy(new_text)
    concerns: List[str] = []

    text = (new_text or "").strip()

    if not any(f in text.lower() for f in PERMITTED_FRAMINGS):
        concerns.append(
            "This does not use one of the usual framings such as 'some people notice' "
            "or 'often go together'. Worth a second look that it still reads as a "
            "question rather than a claim.")

    if "?" not in text:
        concerns.append("This is not phrased as a question, so it may be hard to answer yes, no, or not sure.")

    grade = reading_grade(text)
    if TARGET_GRADE < grade <= MAX_GRADE:
        concerns.append(
            f"This reads at about grade {grade:.0f}. The target is grade "
            f"{TARGET_GRADE:.0f}; shorter sentences or plainer words would help.")

    # A reworded question that no longer shares any substantive word with the
    # evidence is worth flagging. Deliberately crude: it should nudge, not judge.
    if quoted_sentences:
        stop = {"the", "and", "with", "that", "this", "have", "has", "you", "your",
                "for", "are", "was", "were", "some", "people", "been", "true",
                "notice", "often", "from", "they", "their", "when", "what"}
        quote_words = set()
        for q in quoted_sentences:
            quote_words |= {w for w in re.findall(r"[a-z]{4,}", (q or "").lower()) if w not in stop}
        text_words = {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in stop}
        if quote_words and not (quote_words & text_words):
            concerns.append(
                "This wording shares no term with the quoted evidence. Please confirm it "
                "still reflects what the source actually says.")

    if previous_text and len(text) < len(previous_text.strip()) * 0.4:
        concerns.append("This is much shorter than the previous wording; check nothing important was dropped.")

    return {"blocking": blocking, "concerns": concerns}
