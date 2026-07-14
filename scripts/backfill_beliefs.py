#!/usr/bin/env python3
"""
One-time belief-store backfill (lifecycle foundation).

Converts each existing profile's materialized fields into belief records
(status=confirmed, confidence=1.0, source=form — the form/wizard was the
writer for all pre-lifecycle data; where the legacy `_sources` map shows a
field came from chat extraction, source=chat is preserved), and sets the
initial `lifecycle_stage` column from what the profile already contains.

Idempotent: profiles that already have `beliefs.version` are skipped.
Non-destructive: materialized fields and `_sources` are left untouched.

Usage:
    python3 scripts/backfill_beliefs.py                # dry-run report
    python3 scripts/backfill_beliefs.py --apply
    python3 scripts/backfill_beliefs.py --apply --limit 100

Prereqs:
    1. Apply supabase_migrations/2026_07_15_lifecycle_stage.sql first.
    2. SUPABASE_URL + SUPABASE_SERVICE_KEY in the environment.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "lib"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from patient_model import BELIEFS_VERSION, _now_iso, _slug, ensure_beliefs  # noqa: E402
from supabase_client import get_admin_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_beliefs")

_SCALAR_PATHS: Tuple[Tuple[str, str], ...] = (
    # (profile section, field)
    ("patient", "firstName"), ("patient", "age"), ("patient", "sex"),
    ("patient", "zipCode"), ("patient", "ecog"), ("patient", "weight"),
    ("patient", "heightFt"), ("patient", "heightIn"), ("patient", "race_ethnicity"),
    ("patient", "allergies"),
    ("primaryDiagnosis", "site"), ("primaryDiagnosis", "stage"),
    ("primaryDiagnosis", "histology"),
)


def _mk_belief(value: Any, source: str) -> Dict[str, Any]:
    now = _now_iso()
    return {
        "value": value, "confidence": 1.0, "status": "confirmed",
        "source": source, "session_id": None,
        "first_observed": now, "last_updated": now, "confirmed_at": now,
        "history": [],
    }


def _source_for(sources_map: Dict[str, Any], path: str) -> str:
    entry = sources_map.get(path)
    if isinstance(entry, dict) and entry.get("source_type") == "chat":
        return "chat"
    return "form"


def build_beliefs(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the initial beliefs.fields map from materialized profile data."""
    sources_map = profile.get("_sources") or {}
    fields: Dict[str, Any] = {}

    for section, key in _SCALAR_PATHS:
        val = (profile.get(section) or {}).get(key)
        if val not in (None, "", []):
            path = f"{section}.{key}"
            fields[path] = _mk_belief(val, _source_for(sources_map, path))

    for marker, result in ((profile.get("primaryDiagnosis") or {}).get("biomarkers") or {}).items():
        if result not in (None, ""):
            path = f"primaryDiagnosis.biomarkers.{str(marker).upper()}"
            fields[path] = _mk_belief(result, _source_for(sources_map, path))

    for c in (profile.get("patient") or {}).get("comorbidities") or []:
        if isinstance(c, str) and c.strip():
            fields[f"patient.comorbidities.{_slug(c)}"] = _mk_belief(c, "form")

    for tx in profile.get("treatments") or []:
        if isinstance(tx, dict):
            name = tx.get("regimen") or tx.get("category")
            if name:
                clean = {k: v for k, v in tx.items() if v not in (None, "", [])}
                fields[f"treatments.{_slug(name)}"] = _mk_belief(clean, "form")

    for sym in profile.get("symptoms") or []:
        if isinstance(sym, str) and sym.strip():
            fields[f"symptoms.{_slug(sym)}"] = _mk_belief(sym.strip(), "form")

    return fields


def initial_stage(profile: Dict[str, Any]) -> str:
    """
    Initial lifecycle stage from existing data (monotonic rules; the canonical
    implementation lands in lib/question_policy.py — keep these in sync).
    """
    patient = profile.get("patient") or {}
    dx = profile.get("primaryDiagnosis") or {}
    treatments = [t for t in (profile.get("treatments") or []) if isinstance(t, dict)]
    biomarkers = {k: v for k, v in (dx.get("biomarkers") or {}).items() if v not in (None, "")}

    site_known = bool(dx.get("site"))
    stage_known = bool(dx.get("stage"))
    if not (site_known and (stage_known or treatments)):
        return "getting_to_know_you"

    known_count = sum([
        bool(patient.get("age")), bool(patient.get("sex")), bool(patient.get("zipCode")),
        site_known, stage_known, bool(dx.get("histology")),
        bool(biomarkers), bool(treatments), bool(profile.get("symptoms")),
    ])
    coverage = known_count / 9.0

    if not (coverage >= 0.6 and biomarkers and treatments):
        return "understanding_treatment"

    helpful = sum([bool(biomarkers), bool(patient.get("age")),
                   bool(patient.get("sex")), bool(treatments)])
    if patient.get("zipCode") and stage_known and helpful >= 2:
        return "trial_ready"
    return "connected"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform writes (default: dry-run)")
    parser.add_argument("--limit", type=int, default=1000, help="max profiles to scan")
    args = parser.parse_args()

    client = get_admin_client()
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info(f"=== backfill_beliefs ({mode}) ===")

    rows = (
        client.table("patient_profiles")
        .select("user_id, raw_profile")
        .limit(args.limit)
        .execute()
    ).data or []

    stats = {"scanned": len(rows), "skipped_done": 0, "empty": 0, "backfilled": 0}
    stage_counts: Dict[str, int] = {}

    for row in rows:
        user_id = row["user_id"]
        profile = row.get("raw_profile") or {}
        if not isinstance(profile, dict) or not profile:
            stats["empty"] += 1
            continue
        if (profile.get("beliefs") or {}).get("version") == BELIEFS_VERSION:
            stats["skipped_done"] += 1
            continue

        fields = build_beliefs(profile)
        stage = initial_stage(profile)
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

        logger.info(f"  user …{str(user_id)[-6:]}: {len(fields)} beliefs, stage={stage}")

        if args.apply:
            beliefs = ensure_beliefs(profile)
            beliefs["fields"] = fields
            update: Dict[str, Any] = {"raw_profile": profile}
            try:
                client.table("patient_profiles").update(
                    {**update, "lifecycle_stage": stage}
                ).eq("user_id", user_id).execute()
            except Exception as e:
                # lifecycle_stage column may not exist yet — write beliefs alone.
                logger.warning(f"    lifecycle_stage write failed ({e}); writing beliefs only")
                client.table("patient_profiles").update(update).eq("user_id", user_id).execute()
            stats["backfilled"] += 1

    logger.info(f"\nStats: {stats}")
    logger.info(f"Stage distribution: {stage_counts}")
    if not args.apply:
        logger.info("(dry-run — no writes performed; re-run with --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
