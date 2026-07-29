"""Re-anchoring a near-miss quotation to the source's own words (owner
decision D6).

THE GUARANTEE THIS PRESERVES. A stored citation is always text copied out of
the source document. Nothing a model wrote is ever stored as a quotation.

What changes is only how we FIND the sentence the model meant. If a model
returns the right sentence with its capitalisation changed or its double
spaces tidied, the old behaviour discarded a real citation. Now we locate that
sentence and store THE DOCUMENT'S bytes at that position, discarding the
model's approximation entirely.

So this is not a relaxation of the citation check. Every quotation still has
to pass exact matching — it passes because it came out of the source. The
database trigger and the publication re-check, both exact and both unchanged,
are what prove that independently of this module.

WHAT IS DELIBERATELY NOT DONE HERE. No edit distance, no token overlap, no
"close enough" scoring, no model asked to adjudicate. The only differences
bridged are case, whitespace runs, and typographic variants of the same
character — each a bounded, mechanical equivalence. A model that dropped a
word or changed one has not quoted the sentence, and no repair is attempted.
"""

import re
import unicodedata
from typing import Dict, List, NamedTuple, Optional, Tuple

# Characters a model routinely substitutes for the source's own. Mapping these
# is safe because the result is only used to LOCATE text, never to store it.
_EQUIVALENTS: Dict[str, str] = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", " ": " ",
    "ﬁ": "fi", "ﬂ": "fl",
}

# Below this, a normalised match is too easy to land in the wrong place, and a
# fragment that short is not a citation worth repairing.
MIN_REPAIRABLE_CHARS = 20


class Anchor(NamedTuple):
    """A quotation as it appears IN THE SOURCE."""

    quoted_sentence: str   # the document's own bytes, never the model's
    char_offset: int
    repaired: bool         # False when the model quoted it exactly


def _fold(text: str) -> Tuple[str, List[int]]:
    """Case-folded, whitespace-collapsed text plus a map back to the original.

    index_map[i] is the ORIGINAL index the i-th folded character came from,
    which is what makes it possible to recover the source's exact span.
    """
    out: List[str] = []
    index_map: List[int] = []
    in_space = False

    for i, ch in enumerate(text):
        mapped = _EQUIVALENTS.get(ch, ch)
        if mapped.isspace():
            if in_space or not out:
                # Collapse the run; also drop leading whitespace so a quote
                # starting mid-run still anchors.
                in_space = True
                continue
            out.append(" ")
            index_map.append(i)
            in_space = True
            continue
        in_space = False
        folded = mapped.casefold()
        # A ligature folds to more than one character; every resulting
        # character points back at the same original index.
        for c in folded:
            out.append(c)
            index_map.append(i)

    return "".join(out), index_map


def anchor_quote(section_text: str, model_quote: str) -> Optional[Anchor]:
    """Locate `model_quote` in `section_text` and return the SOURCE's text.

    Returns None when the sentence cannot be found, which stays the common and
    correct outcome for a fabricated citation.
    """
    if not section_text or not model_quote or not model_quote.strip():
        return None

    # Fast path: the model quoted it properly.
    exact = section_text.find(model_quote)
    if exact >= 0:
        return Anchor(model_quote, exact, repaired=False)

    if len(model_quote.strip()) < MIN_REPAIRABLE_CHARS:
        return None

    folded_section, index_map = _fold(section_text)
    folded_quote, _ = _fold(model_quote)
    if not folded_quote:
        return None

    pos = folded_section.find(folded_quote)
    if pos < 0:
        return None

    start = index_map[pos]
    end = index_map[pos + len(folded_quote) - 1] + 1
    recovered = section_text[start:end]

    # Self-check: what we are about to store must itself pass the exact test
    # at the offset we are about to store. If it does not, we do not store it.
    if section_text.find(recovered) < 0 or section_text[start:start + len(recovered)] != recovered:
        return None

    return Anchor(recovered, start, repaired=True)


def normalised_equal(a: str, b: str) -> bool:
    """True when two strings differ only by case, whitespace runs, or
    typographic variants. Exposed for tests and reporting, never used to
    decide what gets stored."""
    return _fold(a)[0] == _fold(b)[0]
