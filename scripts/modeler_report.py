#!/usr/bin/env python3
"""
Modeler review report — the human gate for FEATURE_MODELER_ACTIVE.

Renders each patient's connections graph as a readable markdown document
(edges by status, Mermaid sketch, expectations, calibration, reflections,
auto-filled flip checklist) for supervisor review (Dr. Csiki). De-identified:
pseudonymous user prefixes only, and the whole document is self-scanned with
detect_pii_leaks before it is written.

Usage:
  python3 scripts/modeler_report.py --all
  python3 scripts/modeler_report.py --user <uuid>
  python3 scripts/modeler_report.py --user <uuid> --json graph.json  # viz export
  (writes to scripts/eval/reports/modeler/ unless --stdout)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'lib'))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_REPO_ROOT, '.env'))

REPORT_DIR = os.path.join(_REPO_ROOT, 'scripts', 'eval', 'reports', 'modeler')

# Flip-gate thresholds (mirrors the plan's checklist).
GATE_MIN_RESOLVED = 10
GATE_MIN_HIT_RATE = 0.6


def _pseudo(user_id: str) -> str:
    return f"patient-{user_id[-6:]}"


def _mermaid(edges: List[dict]) -> str:
    """Small Mermaid sketch of the strongest edges (Mermaid-safe labels)."""
    def clean(text: str) -> str:
        return "".join(ch for ch in str(text) if ch.isalnum() or ch in " -")[:28]

    lines = ["```mermaid", "graph LR"]
    style = {"corroborated": "==>", "hypothesis": "-->", "refuted": "-.->"}
    for e in sorted(edges, key=lambda x: float(x.get("strength", 0)), reverse=True)[:12]:
        arrow = style.get(e.get("status"), "-->")
        src_id = clean(e["src"].get("key", "src")).replace(" ", "_") or "src"
        dst_id = clean(e["dst"].get("key", "dst")).replace(" ", "_") or "dst"
        lines.append(f'  {src_id}["{clean(e["src"].get("label"))}"] '
                     f'{arrow}|{e.get("rel", "")}| '
                     f'{dst_id}["{clean(e["dst"].get("label"))}"]')
    lines.append("```")
    return "\n".join(lines)


def _edges_table(edges: List[dict], status: str) -> str:
    rows = [e for e in edges if e.get("status") == status]
    if not rows:
        return "_none_"
    out = ["| link | rel | strength | seen | evidence kinds |", "|---|---|---|---|---|"]
    for e in sorted(rows, key=lambda x: float(x.get("strength", 0)), reverse=True):
        kinds = ", ".join(sorted({ev.get("kind", "?") for ev in e.get("evidence", [])}))
        out.append(f"| {e['src'].get('label')} → {e['dst'].get('label')} "
                   f"| {e.get('rel')} | {e.get('strength')} | {e.get('times_seen', 1)}× | {kinds} |")
    return "\n".join(out)


def _expectations_table(expectations: List[dict]) -> str:
    if not expectations:
        return "_none_"
    out = ["| statement | basis | window | status |", "|---|---|---|---|"]
    for x in expectations:
        window = x.get("window") or {}
        out.append(f"| {x.get('statement')} | {x.get('basis')} "
                   f"| {str(window.get('opens', ''))[:10]} → {str(window.get('closes', ''))[:10]} "
                   f"| **{x.get('status')}** |")
    return "\n".join(out)


def _flip_checklist(connections: dict, run_events: List[dict]) -> str:
    calibration = connections.get("calibration") or {}
    resolved = calibration.get("hits", 0) + calibration.get("misses", 0) + calibration.get("expired", 0)
    hit_rate = calibration.get("hit_rate")
    statuses = [((e.get("payload") or {}).get("status")) for e in run_events]
    ok_runs = statuses.count("ok")
    pii_aborts = sum(1 for e in run_events
                     if ((e.get("payload") or {}).get("status")) == "pii_guard")
    reject_totals = sum(sum(((e.get("payload") or {}).get("rejects") or {}).values())
                        for e in run_events)

    def mark(passed: Optional[bool]) -> str:
        return "✅" if passed else ("❌" if passed is False else "⏳")

    guideline = (calibration.get("by_basis") or {}).get("guideline", {})
    observed = (calibration.get("by_basis") or {}).get("observed_pattern", {})

    def basis_rate(stats: dict) -> Optional[float]:
        total = stats.get("hits", 0) + stats.get("misses", 0) + stats.get("expired", 0)
        return round(stats.get("hits", 0) / total, 2) if total else None

    g_rate, o_rate = basis_rate(guideline), basis_rate(observed)
    basis_sane = None if (g_rate is None or o_rate is None) else (g_rate >= o_rate)

    return "\n".join([
        f"- {mark(pii_aborts == 0)} zero `pii_guard` aborts (saw {pii_aborts})",
        f"- {mark(resolved >= GATE_MIN_RESOLVED)} ≥{GATE_MIN_RESOLVED} resolved expectations "
        f"(saw {resolved})",
        f"- {mark(hit_rate is not None and hit_rate >= GATE_MIN_HIT_RATE)} hit-rate "
        f"≥{GATE_MIN_HIT_RATE} (saw {hit_rate})",
        f"- {mark(basis_sane)} guideline-basis hit-rate ≥ observed-pattern "
        f"(guideline {g_rate}, observed {o_rate})",
        f"- ⏳ parse_rejected rate <10% of runs (rejected items {reject_totals} across "
        f"{len(run_events)} runs, {ok_runs} ok)",
        "- ⏳ Dr. Csiki sign-off (plausibility, no hallucinated links, reflection quality)",
    ])


def render_report(user_id: str, profile: dict, run_events: List[dict]) -> str:
    from modeler import ensure_connections
    connections = ensure_connections(profile)
    meta = connections["meta"]
    edges = connections["edges"]
    calibration = connections["calibration"]

    dx = profile.get("primaryDiagnosis") or {}
    stage_line = (profile.get("model_state") or {}).get("lifecycle_stage", "getting_to_know_you")

    parts = [
        f"# Modeler review — {_pseudo(user_id)}",
        f"_Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC · "
        f"cancer: {dx.get('site') or 'n/a'} · lifecycle: {stage_line} · "
        f"runs: {meta.get('run_count', 0)} (last {str(meta.get('last_run_at', ''))[:10]}, "
        f"status {meta.get('last_run_status')}) · model: {meta.get('model')}_",
        "",
        "## Graph sketch", _mermaid(edges) if edges else "_no edges yet_",
        "",
        "## Corroborated edges", _edges_table(edges, "corroborated"),
        "", "## Hypotheses", _edges_table(edges, "hypothesis"),
        "", "## Refuted", _edges_table(edges, "refuted"),
        "",
        "## Expectations", _expectations_table(connections["expectations"]),
        "",
        "## Calibration",
        f"- hits **{calibration.get('hits', 0)}** · misses **{calibration.get('misses', 0)}** · "
        f"expired **{calibration.get('expired', 0)}** · open {calibration.get('open', 0)} · "
        f"hit-rate **{calibration.get('hit_rate')}**",
        f"- by basis: `{json.dumps(calibration.get('by_basis') or {})}`",
        "",
        "## Reflections",
    ]
    reflections = connections["reflections"]
    if reflections:
        for r in reflections:
            belief = r.get("proposed_belief")
            parts.append(f"- [{r.get('status')}] {r.get('statement')}"
                         + (f" → proposes `{belief['path']}` = `{belief['value']}`" if belief else "")
                         + f"\n  - rationale: {r.get('rationale')}")
    else:
        parts.append("_none_")
    parts.extend(["", "## Flip checklist (FEATURE_MODELER_ACTIVE gate)",
                  _flip_checklist(connections, run_events)])
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Modeler review report (markdown).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user", help="single user uuid")
    group.add_argument("--all", action="store_true", help="all users with profiles")
    parser.add_argument("--stdout", action="store_true", help="print instead of writing files")
    parser.add_argument("--json", help="also export the raw graph JSON to this path (single user)")
    args = parser.parse_args()

    from deidentify import detect_pii_leaks
    from supabase_storage import get_admin_client, load_patient_events, load_profile

    if args.all:
        rows = get_admin_client().table("patient_profiles").select("user_id").execute().data or []
        user_ids = [r["user_id"] for r in rows]
    else:
        user_ids = [args.user]

    os.makedirs(REPORT_DIR, exist_ok=True)
    written = 0
    for uid in user_ids:
        profile = load_profile(uid)
        if not profile:
            print(f"{_pseudo(uid)}: no profile, skipped")
            continue
        run_events = load_patient_events(uid, limit=100, kinds=["modeler_run"])
        report = render_report(uid, profile, run_events)

        # Self-scan. Date patterns are exempt: window/run dates are
        # system-generated and a review document needs them absolute (DOBs
        # can't reach the report — the belief digest skiplists identity paths).
        # Names, phones, emails, addresses, zips still redact the report.
        leaks = [(name, s) for name, s in detect_pii_leaks(report)
                 if not name.startswith("full_date")]
        if leaks:
            types = sorted({name for name, _s in leaks})
            report = ("> ⚠️ REDACTED: the generated report tripped the PII guard "
                      f"(types: {', '.join(types)}). Investigate before sharing.\n")
            print(f"{_pseudo(uid)}: PII guard hit ({', '.join(types)}) — report redacted")

        if args.json and not args.all:
            with open(args.json, "w") as f:
                json.dump({"connections": (profile.get("connections") or {})}, f, indent=2)
            print(f"graph JSON → {args.json}")

        if args.stdout:
            print("\n" + report + "\n")
        else:
            path = os.path.join(REPORT_DIR,
                                f"{_pseudo(uid)}_{datetime.utcnow().strftime('%Y%m%d')}.md")
            with open(path, "w") as f:
                f.write(report + "\n")
            print(f"{_pseudo(uid)} → {path}")
        written += 1
    print(f"\n{written} report(s) generated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
