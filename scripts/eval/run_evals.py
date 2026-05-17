#!/usr/bin/env python3
"""
Per-cancer eval harness CLI.

Two modes:
  --mode dry  (default)  exercises retrieval + filters + prompt assembly
                          without making a real LLM call. Cheap; great
                          for CI smoke and for regression-checking the
                          architectural refactor.
  --mode llm              fires real Together AI / Groq calls + the
                          two-pass verifier. Costs tokens. Use for
                          quality gates before flipping a cancer's
                          `ready: true`.

Example:
  python scripts/eval/run_evals.py --cancer colorectal --suite all
  python scripts/eval/run_evals.py --cancer colorectal --suite golden,safety --mode llm
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))
# lib/ also needs to be on sys.path because lib/supabase_storage.py does
# `from supabase_client import …` (no `lib.` prefix), assuming the legacy
# Flask/Vercel-style import root.
sys.path.insert(0, str(_REPO_ROOT / "lib"))

from lib import cancer_registry as registry  # noqa: E402
from lib.confidence import is_in_oncology_domain, route_to_corpus  # noqa: E402
from lib.pdf_utils import hybrid_search  # noqa: E402

from scripts.eval import metrics  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
logger = logging.getLogger("eval")

_ROOT = Path(__file__).resolve().parent
_SUITES_DIR = _ROOT / "suites"
_REPORTS_DIR = _ROOT / "reports"

_DEFAULT_THRESHOLDS = {
    "off_topic_accuracy":   0.95,
    "route_accuracy":       0.85,
    "retrieval_coverage":   0.80,
    "citation_validity":    0.95,
    "escalation_accuracy":  0.95,
    "keyword_compliance":   0.80,
}

# Dry mode lowers tier-1 accuracy expectation because retrieval-similarity
# fallback isn't available without chunks — a few cancer-specific queries
# (e.g. "FOLFOX vs FOLFIRI") that pass in production via retrieval are
# expected to fall through in dry mode.
_DRY_MODE_THRESHOLD_OVERRIDES = {
    "off_topic_accuracy": 0.80,
}

# Metrics that need real LLM answer text. Skipped in --mode dry.
_LLM_ONLY_METRICS = {"escalation_accuracy", "keyword_compliance", "citation_validity"}
# Metrics that need at least one chunk loaded. Skipped (no-fail) when
# retrieval came up empty (e.g. backend unreachable in dry mode).
_CHUNK_DEPENDENT_METRICS = {"route_accuracy", "retrieval_coverage"}


def load_suite(cancer: str, suite: str) -> Dict[str, Any]:
    p = _SUITES_DIR / cancer / f"{suite}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"Suite missing: {p}")
    with p.open() as f:
        return yaml.safe_load(f) or {}


def _load_all_chunks_quiet() -> List[Any]:
    try:
        from supabase_storage import load_all_chunks
    except Exception:
        try:
            from lib.supabase_storage import load_all_chunks
        except Exception:
            return []
    try:
        return load_all_chunks() or []
    except Exception as e:
        logger.warning("Chunk load failed (running without retrieval): %s", e)
        return []


def run_prompt(prompt: Dict[str, Any], cancer: str, chunks: List[Any], mode: str) -> Dict[str, Any]:
    """Execute a single prompt in the requested mode and return a result dict."""
    query = prompt["query"]
    pid = prompt.get("id", query[:40])

    # Tier 1 — in-domain gate
    retrieved = []
    if chunks:
        try:
            retrieved = hybrid_search(query, chunks, top_k=5, cancer_types=[cancer, "general"])
        except Exception as e:
            logger.warning("[%s] retrieval failed: %s", pid, e)
    in_domain, tier1_reason = is_in_oncology_domain(query, retrieved)

    # Tier 2 — corpus routing (only if in-domain)
    route = None
    tier2_reason = ""
    if in_domain:
        route, tier2_reason = route_to_corpus(query, retrieved, selected_cancer=cancer)

    rejected = not in_domain

    result = {
        "id": pid,
        "query": query,
        "expect": prompt.get("expect") or {},
        "in_domain": in_domain,
        "tier1_reason": tier1_reason,
        "route": route,
        "tier2_reason": tier2_reason,
        "rejected": rejected,
        "sources": retrieved,
        "answer": "",
        "mode": mode,
    }

    if mode == "llm" and not rejected:
        # Heavy path — exercise the real LLM stack via the same code paths
        # the API uses. Imports inside the function so dry mode never
        # needs the LLM clients.
        try:
            from llm_utils import assemble_prompt, call_llm
            patient_context = {"cancer_slug": cancer}
            # NOTE: assemble_prompt signature is (message, retrieved, patient,
            # response_length, conversation_context, patient_context) — keyword
            # args to keep this robust against future signature changes.
            prompt_text, _meta = assemble_prompt(
                message=query,
                retrieved=retrieved,
                patient=patient_context,
                response_length="normal",
                patient_context=patient_context,
            )
            answer, _api = call_llm(
                prompt_text,
                response_length="normal",
                query=query,
                cancer_slug=cancer,
            )
            result["answer"] = answer or ""
        except Exception as e:
            logger.warning("[%s] LLM call failed: %s", pid, e)
            result["answer"] = ""

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-cancer eval harness.")
    parser.add_argument("--cancer", required=True, help="Cancer slug (e.g. colorectal).")
    parser.add_argument(
        "--suite",
        required=True,
        help="Suite name(s) — comma-separated; or 'all'. "
             "Suites: golden, off_topic, cross_cutting, safety.",
    )
    parser.add_argument("--mode", choices=("dry", "llm"), default="dry")
    parser.add_argument("--report", type=str, default=None,
                        help="Write JSONL report to this dir (defaults to scripts/eval/reports).")
    args = parser.parse_args()

    if not registry.exists(args.cancer):
        logger.error("Unknown cancer slug: %s", args.cancer)
        return 2

    suites = []
    if args.suite == "all":
        suites = ["golden", "off_topic", "cross_cutting", "safety"]
    else:
        suites = [s.strip() for s in args.suite.split(",") if s.strip()]

    chunks = _load_all_chunks_quiet()
    if not chunks:
        logger.warning("No chunks loaded — retrieval-coverage and tier-2 routing will be limited.")

    all_results = []
    for suite in suites:
        try:
            spec = load_suite(args.cancer, suite)
        except FileNotFoundError as e:
            logger.error("%s", e)
            return 2
        prompts = spec.get("prompts") or []
        logger.info("Running suite=%s (%d prompts) for cancer=%s mode=%s",
                    suite, len(prompts), args.cancer, args.mode)
        for p in prompts:
            r = run_prompt(p, args.cancer, chunks, args.mode)
            r["suite"] = suite
            all_results.append(r)

    # Compute metrics
    summary = {
        "cancer": args.cancer,
        "suites": suites,
        "mode": args.mode,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metrics": {},
    }
    failed = False
    chunks_loaded = bool(chunks)
    for fn in metrics.ALL_METRICS:
        m = fn(all_results)
        summary["metrics"][m["metric"]] = {k: v for k, v in m.items() if k != "detail"}
        threshold = _DEFAULT_THRESHOLDS.get(m["metric"], 0)
        if args.mode == "dry":
            threshold = _DRY_MODE_THRESHOLD_OVERRIDES.get(m["metric"], threshold)
        # Skip enforcement when this metric can't be meaningfully measured
        # in the current mode/environment.
        skipped_reason = None
        if args.mode == "dry" and m["metric"] in _LLM_ONLY_METRICS:
            skipped_reason = "SKIPPED (dry mode — needs LLM answers)"
        elif not chunks_loaded and m["metric"] in _CHUNK_DEPENDENT_METRICS:
            skipped_reason = "SKIPPED (no chunks loaded)"
        if skipped_reason:
            print(f"  {m['metric']:24s} {skipped_reason}")
            continue
        passed_thresh = m["total"] == 0 or m["value"] >= threshold
        print(f"  {m['metric']:24s} {m['value']:.2%}  ({m['pass']}/{m['total']})  threshold={threshold:.0%}  {'PASS' if passed_thresh else 'FAIL'}")
        if not passed_thresh:
            failed = True
            if m["detail"]:
                for d in m["detail"][:3]:
                    print(f"      - {d}")

    # Report
    report_dir = Path(args.report) if args.report else _REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"{args.cancer}_{'-'.join(suites)}_{args.mode}_{stamp}.jsonl"
    with report_path.open("w") as f:
        f.write(json.dumps({"_summary": summary}) + "\n")
        for r in all_results:
            payload = dict(r)
            # Trim sources to id-only to keep the JSONL readable
            payload["sources"] = [
                {"filename": (s.get("filename") if isinstance(s, dict) else None),
                 "chunk_index": (s.get("chunk_index") if isinstance(s, dict) else None),
                 "cancer_types": (s.get("cancer_types") if isinstance(s, dict) else None)}
                for s in (r.get("sources") or [])
            ]
            f.write(json.dumps(payload) + "\n")
    logger.info("Wrote report → %s", report_path)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
