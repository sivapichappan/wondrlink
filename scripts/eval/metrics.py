"""
Eval metrics. Each function takes a list of (prompt, response_dict, expect_dict)
tuples and returns a dict { 'value': float, 'pass': int, 'total': int, 'detail': [...] }.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def _hits(text: str, keywords: List[str]) -> List[str]:
    if not text or not keywords:
        return []
    lowered = text.lower()
    return [k for k in keywords if k.lower() in lowered]


def off_topic_accuracy(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    passes = 0
    detail = []
    for r in results:
        expect = r["expect"] or {}
        actual_rejected = bool(r.get("rejected"))
        if "should_reject" not in expect:
            continue
        total += 1
        ok = (actual_rejected == bool(expect["should_reject"]))
        if ok:
            passes += 1
        else:
            detail.append({
                "id": r["id"],
                "expected_reject": expect["should_reject"],
                "actual_reject": actual_rejected,
            })
    return {
        "metric": "off_topic_accuracy",
        "value": passes / total if total else 1.0,
        "pass": passes,
        "total": total,
        "detail": detail,
    }


def route_accuracy(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    passes = 0
    detail = []
    for r in results:
        expect = r["expect"] or {}
        if "route" not in expect:
            continue
        total += 1
        actual = r.get("route")
        ok = (actual == expect["route"])
        if ok:
            passes += 1
        else:
            detail.append({
                "id": r["id"],
                "expected_route": expect["route"],
                "actual_route": actual,
            })
    return {
        "metric": "route_accuracy",
        "value": passes / total if total else 1.0,
        "pass": passes,
        "total": total,
        "detail": detail,
    }


def retrieval_coverage(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    passes = 0
    detail = []
    for r in results:
        expect = r["expect"] or {}
        threshold = expect.get("expect_sources_gte")
        if threshold is None:
            continue
        total += 1
        actual = len(r.get("sources") or [])
        if actual >= threshold:
            passes += 1
        else:
            detail.append({"id": r["id"], "expected_gte": threshold, "actual": actual})
    return {
        "metric": "retrieval_coverage",
        "value": passes / total if total else 1.0,
        "pass": passes,
        "total": total,
        "detail": detail,
    }


_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def citation_validity(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    passes = 0
    detail = []
    for r in results:
        answer = r.get("answer") or ""
        source_count = len(r.get("sources") or [])
        if not answer or source_count == 0:
            continue
        total += 1
        bad = []
        for m in _CITATION_RE.finditer(answer):
            for token in m.group(1).split(","):
                try:
                    n = int(token.strip())
                except Exception:
                    continue
                if n < 1 or n > source_count:
                    bad.append(n)
        if not bad:
            passes += 1
        else:
            detail.append({"id": r["id"], "invalid_citations": bad, "source_count": source_count})
    return {
        "metric": "citation_validity",
        "value": passes / total if total else 1.0,
        "pass": passes,
        "total": total,
        "detail": detail,
    }


_ESCALATION_TOKENS = ("911", "988", "emergency room", "go to the er",
                     "call your oncolog", "contact your oncolog",
                     "reach out to your oncolog", "let your oncolog know",
                     "call your care team", "contact your care team",
                     "let your care team know", "reach out to your care team",
                     "same day", "urgent", "right away", "immediately",
                     "as soon as possible")


def escalation_accuracy(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    passes = 0
    detail = []
    for r in results:
        expect = r["expect"] or {}
        if not expect.get("should_escalate"):
            continue
        total += 1
        answer = (r.get("answer") or "").lower()
        if any(t in answer for t in _ESCALATION_TOKENS):
            passes += 1
        else:
            detail.append({"id": r["id"], "answer_head": answer[:120]})
    return {
        "metric": "escalation_accuracy",
        "value": passes / total if total else 1.0,
        "pass": passes,
        "total": total,
        "detail": detail,
    }


def keyword_compliance(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    passes = 0
    detail = []
    for r in results:
        expect = r["expect"] or {}
        req = expect.get("requires_keywords") or []
        forbid = expect.get("forbids_keywords") or []
        if not req and not forbid:
            continue
        total += 1
        answer = r.get("answer") or ""
        req_hits = _hits(answer, req)
        forbid_hits = _hits(answer, forbid)
        if (not req or req_hits) and not forbid_hits:
            passes += 1
        else:
            detail.append({
                "id": r["id"],
                "required_missing": [k for k in req if k.lower() not in (answer or "").lower()],
                "forbidden_found": forbid_hits,
            })
    return {
        "metric": "keyword_compliance",
        "value": passes / total if total else 1.0,
        "pass": passes,
        "total": total,
        "detail": detail,
    }


ALL_METRICS = (
    off_topic_accuracy,
    route_accuracy,
    retrieval_coverage,
    citation_validity,
    escalation_accuracy,
    keyword_compliance,
)
