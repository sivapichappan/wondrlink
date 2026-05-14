#!/usr/bin/env python3
"""
One-time backfill: tag every existing pdf_chunks row with the
multi-cancer metadata (cancer_types, doc_type, audience, guideline_org)
derived from its filename.

Idempotent — rows already tagged with the same metadata are skipped.

Prereqs:
    1. Apply supabase_migrations/2026_05_14_chunks_cancer_type.sql FIRST.
    2. Set SUPABASE_URL + SUPABASE_SERVICE_KEY in the environment.

Usage:
    python scripts/backfill_chunk_metadata.py --dry-run    # list filenames and resolved metadata
    python scripts/backfill_chunk_metadata.py --apply      # update all rows
    python scripts/backfill_chunk_metadata.py --apply --filename "CRC_Exercise_Protocols.pdf"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_admin_client  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
logger = logging.getLogger("backfill_chunk_metadata")

_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "_filename_to_metadata.yaml"


def load_map() -> Dict[str, Dict[str, Any]]:
    if not _MAP_PATH.exists():
        raise FileNotFoundError(f"Filename map missing: {_MAP_PATH}")
    with _MAP_PATH.open() as f:
        data = yaml.safe_load(f) or {}
    return data


def resolve_metadata(filename: str, mapping: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Look up metadata for a filename. Default cancer_types=['general'] when unmapped."""
    entry = mapping.get(filename) or {}
    return {
        "cancer_types": entry.get("cancer_types") or ["general"],
        "doc_type": entry.get("doc_type"),
        "audience": entry.get("audience"),
        "guideline_org": entry.get("guideline_org"),
    }


def fetch_filenames(client) -> List[str]:
    # Fetch the list of unique filenames represented in pdf_chunks via pdf_documents.
    try:
        result = client.table("pdf_documents").select("id, filename").execute()
        return [row["filename"] for row in (result.data or []) if row.get("filename")]
    except Exception as e:
        logger.error("Could not fetch pdf_documents: %s", e)
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill pdf_chunks metadata.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="Print resolved metadata per filename; do not write.")
    g.add_argument("--apply", action="store_true", help="Apply the metadata update.")
    parser.add_argument("--filename", type=str, default=None, help="Update only this filename (otherwise: all).")
    args = parser.parse_args()

    mapping = load_map()
    client = get_admin_client()
    filenames = fetch_filenames(client)
    if args.filename:
        filenames = [f for f in filenames if f == args.filename]
        if not filenames:
            logger.error("Filename %r not found in pdf_documents.", args.filename)
            return 2

    unmapped = [f for f in filenames if f not in mapping]
    if unmapped:
        logger.warning(
            "%d filename(s) not in %s — they'll default to cancer_types=['general']: %s",
            len(unmapped), _MAP_PATH.name, unmapped,
        )

    if args.dry_run:
        for fn in filenames:
            meta = resolve_metadata(fn, mapping)
            print(f"{fn}  →  {meta}")
        return 0

    # Resolve doc id for each filename, then bulk update pdf_chunks rows.
    try:
        docs = client.table("pdf_documents").select("id, filename").execute().data or []
    except Exception as e:
        logger.error("Failed to fetch pdf_documents: %s", e)
        return 1

    updated = 0
    failed = 0
    for d in docs:
        fn = d.get("filename")
        if not fn or fn not in filenames:
            continue
        doc_id = d.get("id")
        meta = resolve_metadata(fn, mapping)
        update_payload = {k: v for k, v in meta.items() if v is not None or k == "cancer_types"}
        try:
            client.table("pdf_chunks").update(update_payload).eq("document_id", doc_id).execute()
            updated += 1
            logger.info("Tagged %s → %s", fn, meta)
        except Exception as e:
            failed += 1
            logger.error("Failed to update chunks for %s: %s", fn, e)

    logger.info("Done. docs_updated=%d failed=%d", updated, failed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
