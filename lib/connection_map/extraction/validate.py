"""Validation of extractor output (SPEC §6.1, §6.2; acceptance #11, #12).

Everything a model proposes passes through here before it can become a row.
The functions are pure: they take the model's parsed output plus the facts to
check it against, and return accepted candidates and typed rejections. No
database, no network, no LLM — so the rules that matter are testable without
any of them.

Rejections are counted by reason and reported. §13.1 makes the physician's
rejection mix the pipeline's evaluation signal; these machine-side rejections
are the earlier half of the same idea, and a run that discards 90% of its
output for `quote_not_found` is telling you something specific about the prompt.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Why a candidate was discarded before a human ever saw it.
REJECT_REASONS = (
    "malformed",              # missing or wrong-typed fields
    "unknown_concept",        # slug not in the approved vocabulary
    "unknown_relationship",   # type not in the closed enum
    "self_loop",              # concept related to itself
    "quote_not_found",        # NOT an exact substring of the section
    "empty_quote",
    "duplicate_in_batch",     # the model returned the same triple twice
    "already_exists",         # triple already in the map
    "too_few_evidence",       # pass 2: fewer than two quotations cited
    "unknown_evidence",       # pass 2: cited a quotation id that does not exist
    "duplicate_evidence",     # pass 2: cited the same quotation twice
)

MIN_PASS2_EVIDENCE = 2


class Rejection(Dict[str, Any]):
    pass


def _reject(reason: str, candidate: Any, detail: str = "") -> Dict[str, Any]:
    return {"reason": reason, "candidate": candidate, "detail": detail}


def find_exact_quote(section_text: str, quote: str) -> int:
    """0-based offset of `quote` in `section_text`, or -1.

    EXACT substring search, and it stays exact (§16). No stripping, no case
    folding, no whitespace collapsing, no unicode normalization. A model that
    tidied the sentence it copied has not cited it, and the tidy version is
    precisely what a fabricated citation looks like.
    """
    if not quote or not section_text:
        return -1
    return section_text.find(quote)


def validate_pass1(
    raw: Any,
    section_text: str,
    concept_slugs: Iterable[str],
    relationship_types: Iterable[str],
    existing_triples: Optional[Iterable[Tuple[str, str, str]]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Validate one section's worth of pass-1 output.

    Returns (accepted, rejected). An accepted candidate carries the verified
    `char_offset`, so nothing downstream has to search for the quote again.
    """
    slugs = set(concept_slugs)
    rels = set(relationship_types)
    existing = set(existing_triples or ())
    seen: set = set()

    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for cand in _candidate_list(raw):
        if not isinstance(cand, dict):
            rejected.append(_reject("malformed", cand, "not an object"))
            continue

        src = cand.get("src_concept_slug")
        dst = cand.get("dst_concept_slug")
        rel = cand.get("relationship")
        quote = cand.get("quoted_sentence")

        if not all(isinstance(v, str) and v for v in (src, dst, rel)):
            rejected.append(_reject("malformed", cand, "missing src/dst/relationship"))
            continue
        if not isinstance(quote, str) or not quote.strip():
            rejected.append(_reject("empty_quote", cand))
            continue
        if src not in slugs or dst not in slugs:
            unknown = [s for s in (src, dst) if s not in slugs]
            rejected.append(_reject("unknown_concept", cand, ",".join(unknown)))
            continue
        if rel not in rels:
            rejected.append(_reject("unknown_relationship", cand, rel))
            continue
        if src == dst:
            rejected.append(_reject("self_loop", cand, src))
            continue

        triple = (src, dst, rel)
        if triple in seen:
            rejected.append(_reject("duplicate_in_batch", cand))
            continue
        if triple in existing:
            rejected.append(_reject("already_exists", cand))
            continue

        offset = find_exact_quote(section_text, quote)
        if offset < 0:
            # Acceptance #11. The most important rejection in the pipeline.
            rejected.append(_reject("quote_not_found", cand, quote[:80]))
            continue

        seen.add(triple)
        accepted.append({
            "src_concept_slug": src,
            "dst_concept_slug": dst,
            "relationship": rel,
            "quoted_sentence": quote,
            "char_offset": offset,
            "tier": "A",
            "extraction_pass": 1,
        })

    return accepted, rejected


def validate_pass2(
    raw: Any,
    verified_evidence_ids: Iterable[str],
    concept_slugs: Iterable[str],
    relationship_types: Iterable[str],
    existing_triples: Optional[Iterable[Tuple[str, str, str]]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Validate pass-2 chaining output.

    Pass 2 never introduces a quotation: it may only cite ids that pass 1
    already verified. That is what keeps "every candidate terminates in a
    quotation" (§6.3) true for chained candidates too.
    """
    known = set(verified_evidence_ids)
    slugs = set(concept_slugs)
    rels = set(relationship_types)
    existing = set(existing_triples or ())
    seen: set = set()

    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for cand in _candidate_list(raw):
        if not isinstance(cand, dict):
            rejected.append(_reject("malformed", cand, "not an object"))
            continue

        src = cand.get("src_concept_slug")
        dst = cand.get("dst_concept_slug")
        rel = cand.get("relationship")
        ids = cand.get("evidence_ids")

        if not all(isinstance(v, str) and v for v in (src, dst, rel)):
            rejected.append(_reject("malformed", cand, "missing src/dst/relationship"))
            continue
        if not isinstance(ids, (list, tuple)):
            rejected.append(_reject("malformed", cand, "evidence_ids is not a list"))
            continue
        if src not in slugs or dst not in slugs:
            rejected.append(_reject("unknown_concept", cand))
            continue
        if rel not in rels:
            rejected.append(_reject("unknown_relationship", cand, rel))
            continue
        if src == dst:
            rejected.append(_reject("self_loop", cand, src))
            continue

        if len(set(ids)) != len(ids):
            rejected.append(_reject("duplicate_evidence", cand))
            continue
        unknown = [i for i in ids if i not in known]
        if unknown:
            # A cited id that does not exist is the chaining equivalent of an
            # invented quotation.
            rejected.append(_reject("unknown_evidence", cand, ",".join(map(str, unknown[:3]))))
            continue
        if len(ids) < MIN_PASS2_EVIDENCE:
            # Acceptance #12.
            rejected.append(_reject("too_few_evidence", cand, str(len(ids))))
            continue

        triple = (src, dst, rel)
        if triple in seen:
            rejected.append(_reject("duplicate_in_batch", cand))
            continue
        if triple in existing:
            rejected.append(_reject("already_exists", cand))
            continue

        seen.add(triple)
        accepted.append({
            "src_concept_slug": src,
            "dst_concept_slug": dst,
            "relationship": rel,
            "evidence_ids": list(ids),
            "reasoning": (cand.get("reasoning") or "").strip(),
            "tier": "B",
            "extraction_pass": 2,
        })

    return accepted, rejected


def rejection_summary(rejected: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """Counts per reason, so a run can be read at a glance (§13.1's habit,
    applied to the machine-side half)."""
    out: Dict[str, int] = {}
    for r in rejected:
        out[r["reason"]] = out.get(r["reason"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _candidate_list(raw: Any) -> List[Any]:
    """Pull the candidate list out of whatever shape the model returned.

    Tolerant about the envelope, strict about the contents: a model wrapping
    its answer differently is a formatting quirk, while a model inventing a
    citation is the thing we exist to catch.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("candidates", "relationships", "results", "items"):
            value = raw.get(key)
            if isinstance(value, list):
                return value
    return []


def parse_model_json(text: str) -> Any:
    """Parse a model response that should be JSON, tolerating code fences."""
    import json

    if not text:
        return None
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    try:
        return json.loads(cleaned)
    except Exception:
        # Last resort: the outermost {...} in the response.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except Exception:
                return None
        return None
