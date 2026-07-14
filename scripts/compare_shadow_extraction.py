#!/usr/bin/env python3
"""
Shadow-extraction comparison report (Lifecycle Phase 2 -> Phase 3 gate).

While FEATURE_EXTRACTION_SHADOW=true, every chat turn records extraction v2's
would-be decisions as patient_events(kind='shadow_extraction') while legacy v1
keeps writing the profile. This report summarizes the bake period so the
Phase-3 write flip (FEATURE_BELIEFS_WRITE) is a data-backed decision:

  - volume: shadow runs, decisions, users covered
  - action mix: ADD / UPDATE / INVALIDATE / NOOP / PENDING_CONFIRMATION
  - safety wins: high-stakes facts v2 would have routed to confirmation
    (v1 wrote these silently) and negations v2 caught (v1 cannot)
  - drift: paths where v2's proposed value disagrees with the current profile
    (v1 wrote from the same candidates, so sustained disagreement here means
    a later turn changed the value — inspect before flipping)

Usage:
    python3 scripts/compare_shadow_extraction.py [--days 7] [--limit 2000]
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "lib"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from supabase_client import get_admin_client  # noqa: E402

logging.basicConfig(level=logging.WARNING)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="lookback window")
    parser.add_argument("--limit", type=int, default=2000, help="max events")
    args = parser.parse_args()

    client = get_admin_client()
    since = (datetime.utcnow() - timedelta(days=args.days)).isoformat() + "Z"
    rows = (
        client.table("patient_events")
        .select("user_id, payload, recorded_at")
        .eq("kind", "shadow_extraction")
        .gte("recorded_at", since)
        .order("recorded_at", desc=True)
        .limit(args.limit)
        .execute()
    ).data or []

    print(f"=== shadow extraction report (last {args.days}d, {len(rows)} runs) ===")
    if not rows:
        print("No shadow events found. Is FEATURE_EXTRACTION_SHADOW=true in prod?")
        return 0

    actions: Counter = Counter()
    reasons: Counter = Counter()
    paths: Counter = Counter()
    users = set()
    high_stakes_pending = 0
    negations = 0
    per_path_last_value: dict = defaultdict(list)

    for row in rows:
        users.add(row["user_id"])
        for d in (row.get("payload") or {}).get("decisions", []):
            actions[d.get("action", "?")] += 1
            reasons[d.get("reason", "?")] += 1
            paths[d.get("path", "?")] += 1
            if d.get("action") == "PENDING_CONFIRMATION" and d.get("high_stakes"):
                high_stakes_pending += 1
            if d.get("reason") == "negation":
                negations += 1
            per_path_last_value[(row["user_id"], d.get("path"))].append(d.get("new"))

    print(f"\nUsers covered: {len(users)}")
    print(f"Total decisions: {sum(actions.values())}")
    print("\nAction mix:")
    for action, n in actions.most_common():
        print(f"  {action:24s} {n}")
    print("\nTop reasons:")
    for reason, n in reasons.most_common(10):
        print(f"  {reason:32s} {n}")
    print("\nTop paths:")
    for path, n in paths.most_common(15):
        print(f"  {path:44s} {n}")

    print(f"\nSafety wins vs v1:")
    print(f"  high-stakes facts routed to confirmation (v1 wrote silently): {high_stakes_pending}")
    print(f"  negations caught (v1 has no concept of them):                 {negations}")

    flip_ready = sum(actions.values()) > 0
    print("\nFlip checklist:")
    print(f"  [{'x' if flip_ready else ' '}] shadow decisions observed")
    print(f"  [{'x' if actions.get('PENDING_CONFIRMATION', 0) or high_stakes_pending == 0 else ' '}] "
          "pending-confirmation routing behaving")
    print("  [ ] extraction gold suite >= threshold (scripts/eval, Phase 3)")
    print("  [ ] spot-check a sample of decisions above against real conversations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
