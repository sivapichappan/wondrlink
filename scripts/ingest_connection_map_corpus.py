#!/usr/bin/env python3
"""
Connection-map corpus ingest (SPEC-connection-map.md §4.2, Phase 1).

Reads config/connection_map/corpus_manifest.yaml and loads each PDF into
source_document / source_section VERBATIM, so citations can later be verified
character for character by the database trigger.

This is NOT scripts/seed_chunks.py and does not touch pdf_documents or
pdf_chunks. The RAG chunker strips lines and drops blank ones by design, which
is right for retrieval and fatal for citation checking.

Usage:
    python3 scripts/ingest_connection_map_corpus.py [--check] [--force] [--only FILE]

    --check   validate the manifest and exit; touches nothing
    --force   re-ingest documents whose content hash is unchanged
    --only    ingest a single manifest entry by file name

Environment:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Note: re-ingesting a document that already has citations fails on purpose
(the evidence foreign key restricts it). That is a governance decision, not
something --force overrides.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.ingest import (  # noqa: E402
    DATA_DIR,
    CorpusStore,
    IngestError,
    ingest_document,
    load_manifest,
    validate_manifest,
)


def extract_pages(pdf_path: Path):
    """Per-page text, exactly as pdfplumber returns it.

    No strip, no normalization, no fallback extractor: a different extractor
    produces different text, which would silently invalidate every offset
    already stored for this document. A PDF pdfplumber cannot read is skipped
    loudly instead.
    """
    import pdfplumber

    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages


def main() -> int:
    args = sys.argv[1:]
    check_only = "--check" in args
    force = "--force" in args
    only = None
    if "--only" in args:
        i = args.index("--only")
        if i + 1 >= len(args):
            print("ERROR: --only needs a file name")
            return 1
        only = args[i + 1]

    manifest = load_manifest()
    errors = validate_manifest(manifest)
    if errors:
        print(f"Manifest invalid ({len(errors)} problem(s)); nothing was written:")
        for e in errors:
            print(f"  - {e}")
        return 1

    documents = manifest["documents"]
    if only:
        documents = [d for d in documents if d["file"] == only]
        if not documents:
            print(f"ERROR: {only!r} is not in the manifest")
            return 1

    print(f"Manifest OK: {len(manifest['documents'])} document(s)")
    if check_only:
        return 0

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return 1

    from supabase import create_client

    store = CorpusStore(create_client(url, key))

    ingested = skipped = failed = 0
    total_sections = 0
    for entry in documents:
        name = entry["file"]
        print(f"\n{name}")
        try:
            pages = extract_pages(DATA_DIR / name)
            result = ingest_document(store, entry, pages, force=force)
        except IngestError as e:
            print(f"  SKIPPED: {e}")
            failed += 1
            continue
        except Exception as e:  # noqa: BLE001 - one bad PDF must not end the run
            print(f"  ERROR: {e}")
            failed += 1
            continue

        if result["status"] == "skipped":
            print("  unchanged (pass --force to re-ingest)")
            skipped += 1
        else:
            print(f"  {result['sections']} section(s), text verified after write")
            ingested += 1
            total_sections += result["sections"]

    print("\n" + "=" * 56)
    print(f"ingested {ingested} · unchanged {skipped} · failed {failed}")
    print(f"sections written: {total_sections}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
