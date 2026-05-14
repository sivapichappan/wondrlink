#!/usr/bin/env python3
"""
One-time profile schema v2 migration.

Backfills patient_profiles rows with the new v2 universal-core columns
(cancer_slug, role, stage_group, treatment_intent, clinical, schema_version)
derived from the existing raw_profile blob.

The migration is idempotent — rows with schema_version='v2' are skipped.
The migration is non-destructive — raw_profile and the legacy denormalized
columns are left in place for the dual-write window.

Usage:
    python scripts/migrate_profiles_v2.py --dry-run     # show what would change for 5 sample rows
    python scripts/migrate_profiles_v2.py --apply       # run against all eligible rows
    python scripts/migrate_profiles_v2.py --apply --limit 100

Prereqs:
    1. Apply supabase_migrations/2026_05_14_profile_v2.sql FIRST.
    2. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict

# Make ./lib importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.profile_validator import (  # noqa: E402
    derive_clinical_payload,
    derive_universal_core,
    validate_clinical,
)
from lib.supabase_client import get_admin_client  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
logger = logging.getLogger("migrate_profiles_v2")


def derive_v2_row(raw_profile: Dict[str, Any]) -> Dict[str, Any]:
    core = derive_universal_core(raw_profile)
    clinical = derive_clinical_payload(raw_profile)
    ok, errors = validate_clinical(core["cancer_slug"], clinical)
    return {
        **core,
        "clinical": clinical if ok else {},
        "schema_version": "v2",
        "_validation_ok": ok,
        "_validation_errors": errors,
    }


def fetch_unmigrated(client, limit: int = None):
    q = client.table("patient_profiles").select("user_id, raw_profile, schema_version")
    # Supabase Python client doesn't support "IS NULL OR != 'v2'" directly in one call.
    # Pull rows where schema_version is null OR not 'v2' by fetching both and merging.
    rows = []
    try:
        null_rows = q.is_("schema_version", "null")
        if limit:
            null_rows = null_rows.limit(limit)
        rows.extend(null_rows.execute().data or [])
    except Exception as e:
        logger.warning("null-schema_version fetch failed: %s", e)
    remaining = (limit - len(rows)) if limit else None
    if remaining is None or remaining > 0:
        try:
            ne_rows_q = client.table("patient_profiles").select("user_id, raw_profile, schema_version").neq(
                "schema_version", "v2"
            )
            if remaining:
                ne_rows_q = ne_rows_q.limit(remaining)
            existing_ids = {r["user_id"] for r in rows}
            for r in ne_rows_q.execute().data or []:
                if r["user_id"] not in existing_ids and r.get("schema_version") is not None:
                    rows.append(r)
                    if limit and len(rows) >= limit:
                        break
        except Exception as e:
            logger.warning("neq-v2 fetch failed: %s", e)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill profile schema v2 columns.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="Show diffs for 5 random rows; do not write.")
    g.add_argument("--apply", action="store_true", help="Write the v2 columns for every eligible row.")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N rows.")
    args = parser.parse_args()

    client = get_admin_client()

    if args.dry_run:
        rows = fetch_unmigrated(client, limit=200)
        if not rows:
            logger.info("Nothing to migrate (no rows with schema_version != 'v2').")
            return 0
        sample = random.sample(rows, min(5, len(rows)))
        for r in sample:
            raw = r.get("raw_profile") or {}
            derived = derive_v2_row(raw)
            print(f"\n--- user_id: {r['user_id']} ---")
            print(f"  cancer_slug:     {derived['cancer_slug']}")
            print(f"  role:            {derived['role']}")
            print(f"  stage_group:     {derived['stage_group']}")
            print(f"  treatment_intent:{derived['treatment_intent']}")
            print(f"  validation_ok:   {derived['_validation_ok']}")
            if derived["_validation_errors"]:
                print(f"  validation errs: {derived['_validation_errors'][:3]}")
            print(f"  clinical:        {json.dumps(derived['clinical'], indent=2)[:500]}{'...' if len(json.dumps(derived['clinical'])) > 500 else ''}")
        print(f"\nDry-run sample of {len(sample)} of {len(rows)} eligible rows.")
        return 0

    rows = fetch_unmigrated(client, limit=args.limit)
    if not rows:
        logger.info("Nothing to migrate.")
        return 0

    migrated = 0
    failed = 0
    for r in rows:
        user_id = r["user_id"]
        raw = r.get("raw_profile") or {}
        try:
            derived = derive_v2_row(raw)
            update_row = {
                "cancer_slug": derived["cancer_slug"],
                "role": derived["role"],
                "stage_group": derived["stage_group"],
                "treatment_intent": derived["treatment_intent"],
                "clinical": derived["clinical"],
                "schema_version": "v2",
            }
            client.table("patient_profiles").update(update_row).eq("user_id", user_id).execute()
            migrated += 1
            if migrated % 50 == 0:
                logger.info("Migrated %d rows so far…", migrated)
        except Exception as e:
            failed += 1
            logger.error("Failed to migrate %s: %s", user_id, e)

    logger.info("Done. migrated=%d failed=%d total=%d", migrated, failed, len(rows))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
