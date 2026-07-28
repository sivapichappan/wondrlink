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
CAUSAL_PATTERNS = (
    (r"\bcauses?\b", "causes"),
    (r"\bcaused by\b", "caused by"),
    (r"\bleads? to\b", "leads to"),
    (r"\bresults? in\b", "results in"),
    (r"\bbecause of\b", "because of"),
    (r"\bdue to\b", "due to"),
    (r"\btriggers?\b", "triggers"),
    (r"\bmakes? you\b", "makes you"),
)

# §8: no numerals expressing confidence or probability.
CONFIDENCE_PATTERNS = (
    r"\b\d+\s*%",
    r"\b\d+\s*(?:in|out of)\s*\d+\b",
    r"\b(?:probability|likelihood|confidence)\b",
    r"\bodds\b",
)

# §8 permits these framings; used only to explain a finding, never to gate.
PERMITTED_FRAMINGS = (
    "some people", "often go together", "worth mentioning to your care team",
    "notice", "seem to go together",
)

EM_DASH = "—"
EN_DASH = "–"

# Grade-6 proxy. A full readability score needs syllable counting that varies
# by implementation; these two thresholds catch what actually goes wrong in
# clinician-written copy, which is long sentences and long words.
MAX_WORDS_PER_SENTENCE = 22
MAX_LONG_WORDS = 3
LONG_WORD_CHARS = 13


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


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
