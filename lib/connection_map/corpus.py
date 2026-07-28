"""Verbatim sectioning of source documents (SPEC-connection-map.md §4.2, §6.1).

Everything downstream of this module depends on one property: the text stored
for a section is a byte-for-byte slice of the document's canonical text. A
citation is verified by exact string comparison at a character offset, so any
strip(), any blank-line drop, any unicode normalization silently invalidates
every quotation taken from that document.

That is exactly why the existing RAG chunker cannot be reused: lib/pdf_utils.py
strips each line and skips empty ones by design (good for retrieval, fatal
here).

Two invariants, both locked by tests:

  1. PARTITION. ''.join(s.text for s in sections) == canonical_text.
     Sections never overlap, never leave gaps, and never drop a character.
  2. OFFSETS. section.text == canonical_text[s.char_start:s.char_end], with
     0-based code-point offsets, so a quote found at Python offset N inside a
     section matches Postgres substr(text, N + 1, len(quote)) in the database
     trigger.

Sectioning therefore only ever chooses CUT POINTS. It never rewrites text.
"""

import re
import unicodedata
from typing import Dict, List, NamedTuple, Sequence

# Page separator inside the canonical text. Form feed is the conventional page
# break, is preserved by JSON and PostgREST, and does not occur in extracted
# PDF text in practice.
PAGE_SEPARATOR = "\f"

# A section shorter than this is merged into the following one rather than
# standing alone: a lone heading line is not a citable section.
MIN_SECTION_CHARS = 200

# Hard ceiling so one unstructured document cannot become a single huge row.
# Splitting happens at a line start, never mid-line.
MAX_SECTION_CHARS = 20000

_HEADING_PATTERNS = (
    r"^[A-Z][A-Z0-9 \-/&,'()]{3,}$",                     # ALL CAPS heading line
    r"^\d+(?:\.\d+)*\.?\s+[A-Z].{0,80}$",                # 1. / 1.2 numbered heading
    r"^(?:Chapter|Section|Part|Appendix)\s+\w+.{0,80}$",  # explicit label
    r"^[A-Z][A-Za-z0-9 \-/&,'()]{2,60}:$",               # Title Case heading with colon
    r"^(?:Background|Introduction|Methods|Results|Discussion|Conclusions?|"
    r"Treatment|Diagnosis|Management|Recommendations?|Guidelines?|Overview|"
    r"Summary|Side Effects?|Follow-?up|Surveillance|Survivorship)\b.{0,80}$",
)

_HEADING_RE = tuple(re.compile(p) for p in _HEADING_PATTERNS)

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


class Section(NamedTuple):
    """A verbatim slice of a document's canonical text."""

    ordinal: int
    section_ref: str
    heading: str  # verbatim heading line, or "" when the section has none
    text: str
    char_start: int
    char_end: int
    page_start: int
    page_end: int


def build_canonical_text(page_texts: Sequence[str]) -> str:
    """Join per-page extracted text into the canonical document text.

    No stripping, no normalization, no re-wrapping. This exact string is what
    offsets are measured against and what content_sha256 is computed over, so
    changing this function invalidates every stored citation.
    """
    return PAGE_SEPARATOR.join(page_texts)


def _page_bounds(canonical: str) -> List[int]:
    """Start offset of each page within the canonical text."""
    bounds = [0]
    for i, ch in enumerate(canonical):
        if ch == PAGE_SEPARATOR:
            bounds.append(i + 1)
    return bounds


def _page_of(offset: int, bounds: Sequence[int]) -> int:
    """1-based page number containing `offset`."""
    page = 1
    for i, start in enumerate(bounds):
        if offset >= start:
            page = i + 1
        else:
            break
    return page


def _is_heading(line: str) -> bool:
    # Match against the line's visible content, but never store the trimmed
    # form: trimming is for detection only.
    probe = line.strip()
    if not probe or len(probe) > 100:
        return False
    if probe.endswith("."):  # a sentence, not a heading
        return False
    return any(rx.match(probe) for rx in _HEADING_RE)


def _slugify(text: str, limit: int = 40) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return _SLUG_STRIP_RE.sub("-", folded.lower()).strip("-")[:limit].strip("-")


def _lines(canonical: str) -> List[tuple]:
    """[(start_offset, line_text), ...] for every line.

    A page separator terminates a line as surely as a newline does: extracted
    page text does not reliably end with "\\n", so without this a heading at
    the top of page 2 would not sit at a line start and could never become a
    cut point.
    """
    out: List[tuple] = []
    start = 0
    end = len(canonical)
    while start <= end:
        nl = canonical.find("\n", start)
        ff = canonical.find(PAGE_SEPARATOR, start)
        stop = min(x for x in (nl, ff) if x != -1) if (nl != -1 or ff != -1) else -1
        if stop == -1:
            out.append((start, canonical[start:]))
            break
        out.append((start, canonical[start:stop]))
        start = stop + 1
    return out


def sectionize(page_texts: Sequence[str]) -> List[Section]:
    """Split a document into verbatim sections.

    Returns [] for an empty document. Cut points are line starts chosen at
    detected headings, subject to MIN/MAX size guards; the text itself is
    passed through untouched.
    """
    canonical = build_canonical_text(page_texts)
    if not canonical:
        return []

    lines = _lines(canonical)
    starts = [start for start, _ in lines]
    line_at = dict(lines)

    # 1. Candidate cuts: every heading line start (plus 0, always).
    cuts = [0]
    for start, line in lines:
        if start and _is_heading(line):
            cuts.append(start)

    # 2. Enforce the minimum size by dropping cuts that would make a runt
    #    section. Dropping a cut merges forward; no character is ever lost.
    kept: List[int] = [0]
    for cut in cuts[1:]:
        if cut - kept[-1] >= MIN_SECTION_CHARS:
            kept.append(cut)

    # 3. Enforce the maximum size by adding cuts at line starts.
    bounded: List[int] = []
    for i, cut in enumerate(kept):
        bounded.append(cut)
        end = kept[i + 1] if i + 1 < len(kept) else len(canonical)
        while end - bounded[-1] > MAX_SECTION_CHARS:
            limit = bounded[-1] + MAX_SECTION_CHARS
            candidates = [s for s in starts if bounded[-1] < s <= limit]
            if not candidates:
                break  # no line start to split on; leave the long section intact
            bounded.append(candidates[-1])

    page_bounds = _page_bounds(canonical)
    sections: List[Section] = []
    for i, start in enumerate(bounded):
        end = bounded[i + 1] if i + 1 < len(bounded) else len(canonical)
        text = canonical[start:end]
        first_line = line_at.get(start, "")
        heading = first_line if _is_heading(first_line) else ""
        slug = _slugify(heading)
        ref = f"s{i:04d}-{slug}" if slug else f"s{i:04d}"
        sections.append(Section(
            ordinal=i,
            section_ref=ref,
            heading=heading,
            text=text,
            char_start=start,
            char_end=end,
            page_start=_page_of(start, page_bounds),
            page_end=_page_of(max(start, end - 1), page_bounds),
        ))
    return sections


def verify_partition(canonical: str, sections: Sequence[Section]) -> List[str]:
    """Check the two invariants. Returns error strings; empty means good.

    Called by the ingester before insert and again after read-back, so a
    document can never carry citations against text that was silently altered
    in transit.
    """
    errors: List[str] = []
    if not sections:
        if canonical:
            errors.append("document produced no sections")
        return errors

    rebuilt = "".join(s.text for s in sections)
    if rebuilt != canonical:
        errors.append(
            f"sections do not reproduce the document: {len(rebuilt)} chars vs {len(canonical)}")

    for i, s in enumerate(sections):
        if s.ordinal != i:
            errors.append(f"section {i}: ordinal is {s.ordinal}")
        if canonical[s.char_start:s.char_end] != s.text:
            errors.append(f"section {i}: text does not match its offsets")
        if s.char_end - s.char_start != len(s.text):
            errors.append(f"section {i}: span does not match text length")
        if i and s.char_start != sections[i - 1].char_end:
            errors.append(f"section {i}: gap or overlap at {s.char_start}")

    refs = [s.section_ref for s in sections]
    if len(set(refs)) != len(refs):
        errors.append("duplicate section_ref within document")

    return errors


def locate_quote(section: Section, quote: str) -> int:
    """0-based code-point offset of `quote` within `section.text`, or -1.

    Exact substring search only. Extraction uses this to produce the
    char_offset the database trigger re-verifies; softening it to fuzzy
    matching here would defeat the trigger's whole purpose (§16).
    """
    if not quote:
        return -1
    return section.text.find(quote)


def section_rows(document_id: str, sections: Sequence[Section]) -> List[Dict]:
    """Sections as insert-ready rows for the source_section table."""
    return [{
        "document_id": document_id,
        "section_ref": s.section_ref,
        "ordinal": s.ordinal,
        "heading": s.heading or None,
        "text": s.text,
        "char_start": s.char_start,
        "char_end": s.char_end,
        "page_start": s.page_start,
        "page_end": s.page_end,
    } for s in sections]
