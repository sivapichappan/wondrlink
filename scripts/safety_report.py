#!/usr/bin/env python3
"""
Weekly safety-classifier review report (supervisor mandate 2026-07-21).

Summarizes the safety_classifications audit table so false positives and
misses can be audited weekly: counts by tier / category / source, latency
percentiles, and the full list of rule_matched = false rows (the
AI-judgment calls) as CATEGORY + TIER + DE-IDENTIFIED RATIONALE only —
message text never leaves the database. Recurring rule_matched = false
categories become "promotion candidates" for the next rules-file version
(v0.9 -> v1.0; physician sign-off is the launch blocker).

The whole report is self-scanned with detect_pii_leaks before it is
written, mirroring scripts/modeler_report.py.

Usage:
  python3 scripts/safety_report.py            # last 7 days
  python3 scripts/safety_report.py --days 30
  python3 scripts/safety_report.py --stdout
"""

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'lib'))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_REPO_ROOT, '.env'))

REPORT_DIR = os.path.join(_REPO_ROOT, 'scripts', 'eval', 'reports', 'safety')

# A rule_matched=false category seen at least this often is proposed for
# promotion into the next rules-file version.
PROMOTION_MIN_COUNT = 3


def _percentile(values: List[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))
    return ordered[idx]


def fetch_rows(days: int) -> List[Dict[str, Any]]:
    from supabase_client import get_admin_client

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    client = get_admin_client()
    resp = (
        client.table('safety_classifications')
        .select('tier,category,confidence,rationale,rule_matched,source,'
                'rules_version,model,latency_ms,created_at')
        .gte('created_at', since)
        .order('created_at', desc=True)
        .limit(5000)
        .execute()
    )
    return resp.data or []


def render_report(rows: List[Dict[str, Any]], days: int) -> str:
    from deidentify import deidentify_conversation_context

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    lines: List[str] = [
        f"# Safety-classifier weekly review — {now} (last {days} days)",
        "",
        f"Total non-NONE classifications: **{len(rows)}**",
        "",
    ]

    if not rows:
        lines.append("_No classifications in the window._")
        return "\n".join(lines)

    rules_versions = sorted({r.get('rules_version') or '?' for r in rows})
    lines.append(f"Rules version(s) in window: {', '.join(rules_versions)}")
    lines.append("")

    # --- Counts ---
    for label, key in (("tier", 'tier'), ("category", 'category'),
                       ("source", 'source')):
        counts = Counter(str(r.get(key) or '?') for r in rows)
        lines.append(f"## By {label}")
        lines.append("")
        lines.append("| value | count |")
        lines.append("|---|---|")
        for value, count in counts.most_common():
            lines.append(f"| {value} | {count} |")
        lines.append("")

    # --- Latency (LLM-involved rows only) ---
    lat = [int(r['latency_ms']) for r in rows if r.get('latency_ms')]
    if lat:
        lines.append("## Classifier latency (LLM calls)")
        lines.append("")
        lines.append(f"p50 = {_percentile(lat, 0.5)} ms · "
                     f"p95 = {_percentile(lat, 0.95)} ms · "
                     f"max = {max(lat)} ms · n = {len(lat)}")
        lines.append("")

    # --- Throttling health ---
    fallback_count = sum(1 for r in rows if r.get('source') == 'rules-fallback')
    if fallback_count:
        share = 100.0 * fallback_count / len(rows)
        lines.append(f"**rules-fallback share: {share:.0f}%** — the LLM layer "
                     "was unavailable for these (throttled or down). If this "
                     "stays high, consider the Groq paid tier or "
                     "MODEL_CLASSIFIER_PROVIDER=together.")
        lines.append("")

    # --- AI-judgment calls (rule_matched = false) ---
    judgment = [r for r in rows if not r.get('rule_matched')]
    lines.append("## AI-judgment escalations (rule_matched = false)")
    lines.append("")
    if not judgment:
        lines.append("_None — every escalation matched a listed rule._")
        lines.append("")
    else:
        lines.append("| tier | category | confidence | rationale (de-identified) |")
        lines.append("|---|---|---|---|")
        for r in judgment:
            rationale = deidentify_conversation_context(
                str(r.get('rationale') or ''))[:160]
            lines.append(f"| {r.get('tier')} | {r.get('category')} | "
                         f"{r.get('confidence')} | {rationale} |")
        lines.append("")

    # --- Promotion candidates ---
    promo = Counter(str(r.get('category') or 'novel') for r in judgment)
    candidates = [(c, n) for c, n in promo.most_common() if n >= PROMOTION_MIN_COUNT]
    lines.append("## Promotion candidates for the next rules version")
    lines.append("")
    if candidates:
        for category, count in candidates:
            lines.append(f"- `{category}` — {count} AI-judgment escalations this "
                         "window; consider a named rule entry")
    else:
        lines.append(f"_None yet (threshold: {PROMOTION_MIN_COUNT} recurrences)._")
    lines.append("")
    lines.append("Physician review of the rules file remains the LAUNCH BLOCKER "
                 "before real patients (SAGE_TODO Workstream S).")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly safety-classifier review")
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--stdout', action='store_true')
    args = parser.parse_args()

    rows = fetch_rows(args.days)
    report = render_report(rows, args.days)

    from deidentify import detect_pii_leaks
    # Self-scan. Date patterns are exempt (same rationale as
    # modeler_report.py): the header/window dates are system-generated and a
    # review document needs them absolute; rationales are de-identified and
    # message text never enters the report. Names, phones, emails,
    # addresses, zips still block it.
    leaks = [(name, s) for name, s in detect_pii_leaks(report)
             if not name.startswith("full_date")]
    if leaks:
        print(f"REFUSING to write: PII guard flagged {len(leaks)} item(s) "
              "in the rendered report.", file=sys.stderr)
        return 1

    if args.stdout:
        print(report)
        return 0

    os.makedirs(REPORT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d')
    path = os.path.join(REPORT_DIR, f"safety_review_{stamp}.md")
    with open(path, 'w') as f:
        f.write(report)
    print(f"Wrote {path} ({len(rows)} classifications)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
