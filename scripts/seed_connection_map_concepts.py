#!/usr/bin/env python3
"""
Connection-map concept seeder (SPEC-connection-map.md §4.1, §10.1, Phase 1).

Loads config/connection_map/concepts_breast.yaml into the concept table.
Idempotent: upserts on slug, so re-running converges rather than duplicating.

Usage:
    python3 scripts/seed_connection_map_concepts.py [--check] [--file PATH]

    --check   validate the YAML and exit; touches nothing

Environment:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

PHASE 1 ONLY, and this will need revisiting: the YAML is the source of truth
right now, so an upsert overwrites every column. From Phase 2 onward
display_patient holds physician-authored wording (§5.4 "Reword"), and
overwriting that would silently discard clinical review. When the review
workspace lands, this seeder must stop clobbering reviewer-curated columns.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.concepts import (  # noqa: E402
    CONCEPTS_DIR,
    concept_rows,
    load_concepts,
    validate_concepts,
)


def main() -> int:
    args = sys.argv[1:]
    check_only = "--check" in args
    path = CONCEPTS_DIR / "concepts_breast.yaml"
    if "--file" in args:
        i = args.index("--file")
        if i + 1 >= len(args):
            print("ERROR: --file needs a path")
            return 1
        path = Path(args[i + 1])

    doc = load_concepts(path)
    errors = validate_concepts(doc)
    if errors:
        print(f"Concept seed invalid ({len(errors)} problem(s)); nothing was written:")
        for e in errors:
            print(f"  - {e}")
        return 1

    rows = concept_rows(doc)
    additions = sum(1 for c in doc["concepts"] if c.get("spec_addition"))
    print(f"{path.name}: {len(rows)} concept(s) valid "
          f"({additions} marked spec_addition)")
    if check_only:
        return 0

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return 1

    from supabase import create_client

    client = create_client(url, key)

    # Warn before overwriting anything a reviewer may have authored.
    try:
        existing = (client.table("concept")
                    .select("slug, display_patient")
                    .in_("slug", [r["slug"] for r in rows])
                    .execute()).data or []
        curated = [r["slug"] for r in existing if r.get("display_patient")]
        if curated:
            print(f"REFUSING: {len(curated)} concept(s) already carry physician-authored "
                  f"display_patient wording; this seeder would overwrite it.")
            print("  Phase 2+ needs a seeder that preserves reviewer-curated columns.")
            return 1
    except Exception as e:  # noqa: BLE001 - table may not exist yet
        print(f"  (pre-check skipped: {e})")

    client.table("concept").upsert(rows, on_conflict="slug").execute()
    print(f"Seeded {len(rows)} concept(s) for cancer={doc['cancer']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
