#!/usr/bin/env python3
"""Copy the connection map from sage-dev to production, once.

    python3 scripts/copy_connection_map_to_prod.py --dry-run
    python3 scripts/copy_connection_map_to_prod.py

The map was built and reviewed on sage-dev because prod has live patients. It has
to move for the physician to review it on her phone, which talks to prod.

WHAT MAKES THIS SAFE TO RUN AGAINST A LIVE DATABASE. It only ever INSERTS into
the connection-map tables, which no patient-facing code path reads (phases 7-9
are not built). It never touches a patient table. It is idempotent: everything is
keyed on the ids it copies, and a second run finds the rows already present.

WHAT MAKES IT SELF-PROVING. Edges go through insert_master_edge_with_evidence,
so prod's own verify trigger re-checks EVERY quotation character for character
against the section text this script just copied. A citation that survived the
move is a citation prod has independently confirmed; one that did not move
correctly cannot be inserted at all. The copy cannot silently corrupt a quotation.

Concept, document and section ids are PRESERVED, because evidence rows point at
section ids and edges point at concept ids. Edge ids are not preserved: the RPC
mints them, and nothing outside evidence references an edge id yet.

Reads sage-dev from .env.development and prod from .env, into separate variables
— sourcing both shells at once collides on SUPABASE_URL and silently points half
the work at the wrong database.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import dotenv_values

_REPO = Path(__file__).resolve().parent.parent

# Sections carry the full verbatim text of a guideline page; a whole-corpus
# payload in one request is megabytes.
SECTION_BATCH = 25
ROW_BATCH = 100


def client(url: str, key: str):
    from supabase import create_client
    return create_client(url, key)


def fetch_all(db, table: str, columns: str, page: int = 1000) -> List[Dict[str, Any]]:
    """PostgREST caps a response; page through so a big table is not silently
    truncated to its first 1000 rows."""
    out: List[Dict[str, Any]] = []
    start = 0
    while True:
        rows = (db.table(table).select(columns)
                .order("id").range(start, start + page - 1).execute()).data or []
        out.extend(rows)
        if len(rows) < page:
            return out
        start += page


def copy_rows(dst, table: str, rows: List[Dict[str, Any]], batch: int, dry: bool) -> int:
    if not rows:
        return 0
    if dry:
        return len(rows)
    written = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        # on_conflict=id so a re-run is a no-op rather than a duplicate-key error.
        dst.table(table).upsert(chunk, on_conflict="id").execute()
        written += len(chunk)
        print(f"    {table}: {written}/{len(rows)}")
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count everything, write nothing")
    args = ap.parse_args()

    dev = dotenv_values(_REPO / ".env.development")
    prod = dotenv_values(_REPO / ".env")
    src_url, src_key = dev.get("SUPABASE_URL"), dev.get("SUPABASE_SERVICE_ROLE_KEY")
    dst_url, dst_key = prod.get("SUPABASE_URL"), prod.get("SUPABASE_SERVICE_ROLE_KEY")
    if not all([src_url, src_key, dst_url, dst_key]):
        print("ERROR: need SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in BOTH .env.development and .env")
        return 1
    if src_url == dst_url:
        print("ERROR: source and destination are the same database")
        return 1

    src, dst = client(src_url, src_key), client(dst_url, dst_key)
    print(f"from {src_url}\n  to {dst_url}")
    print("(inserts only, connection-map tables only; no patient table is touched)\n")

    # --- vocabulary and corpus, ids preserved -------------------------------
    concepts = fetch_all(src, "concept",
                         "id, slug, domain, display_clinical, display_patient, "
                         "terminology_system, terminology_code, instrument, cancer_scopes")
    docs = fetch_all(src, "source_document",
                     "id, title, publisher, edition, scope, cancer, file_path, content_sha256")
    sections = fetch_all(src, "source_section",
                         "id, document_id, section_ref, ordinal, heading, text, "
                         "char_start, char_end, page_start, page_end")
    runs = fetch_all(src, "extraction_run", "id, cancer, pass_number, model, prompt_id, stats")

    # Phase 3 left probe fixtures on sage-dev: two `g_` concepts, a `__gate__`
    # document, and an edge between them that is APPROVED. Copying that edge
    # would put an approved-with-no-attestation row into production, which is
    # precisely the state the publication gate exists to catch — and the state a
    # separate probe already found once. None of it belongs in prod.
    fixture_concepts = {c["id"] for c in concepts if c["slug"].startswith("g_")}
    fixture_docs = {d["id"] for d in docs if "__gate__" in (d["file_path"] or "")}
    concepts = [c for c in concepts if c["id"] not in fixture_concepts]
    docs = [d for d in docs if d["id"] not in fixture_docs]
    sections = [s for s in sections if s["document_id"] not in fixture_docs]
    if fixture_concepts or fixture_docs:
        print(f"excluding Phase 3 probe fixtures: {len(fixture_concepts)} concepts, "
              f"{len(fixture_docs)} document(s) and everything under them")

    print(f"concepts {len(concepts)}   documents {len(docs)}   "
          f"sections {len(sections)}   extraction runs {len(runs)}")

    print("\ncopying vocabulary and corpus:")
    copy_rows(dst, "concept", concepts, ROW_BATCH, args.dry_run)
    copy_rows(dst, "source_document", docs, ROW_BATCH, args.dry_run)
    copy_rows(dst, "source_section", sections, SECTION_BATCH, args.dry_run)
    copy_rows(dst, "extraction_run", runs, ROW_BATCH, args.dry_run)

    # --- edges, through the RPC so prod re-verifies every quotation ---------
    edges = fetch_all(src, "master_edge",
                      "id, src_concept_id, dst_concept_id, relationship, urgency, tier, "
                      "status, candidate_origin, extraction_run_id, extraction_pass, "
                      "prior_alpha, prior_beta, expected_prevalence_low, "
                      "expected_prevalence_high, patient_phrasing, rejection_reason")
    evidence = fetch_all(src, "master_edge_evidence",
                         "id, master_edge_id, source_section_id, source_document_id, "
                         "section_ref, evidence_kind, quoted_sentence, reasoning, "
                         "char_offset, ordinal")
    by_edge: Dict[str, List[Dict[str, Any]]] = {}
    for ev in evidence:
        by_edge.setdefault(ev["master_edge_id"], []).append(ev)

    # Already there? Then this is a re-run.
    existing = {(e["src_concept_id"], e["dst_concept_id"], e["relationship"])
                for e in fetch_all(dst, "master_edge",
                                   "id, src_concept_id, dst_concept_id, relationship")}

    print(f"\ncopying {len(edges)} edges with {len(evidence)} citations "
          f"({len(existing)} already present):")
    moved, skipped, failed = 0, 0, []
    for edge in edges:
        if (edge["src_concept_id"] in fixture_concepts
                or edge["dst_concept_id"] in fixture_concepts):
            skipped += 1
            continue
        triple = (edge["src_concept_id"], edge["dst_concept_id"], edge["relationship"])
        if triple in existing:
            skipped += 1
            continue
        rows = sorted(by_edge.get(edge["id"], []), key=lambda r: r["ordinal"])
        if not rows:
            failed.append((edge["id"], "no evidence on the source side"))
            continue
        if args.dry_run:
            moved += 1
            continue
        try:
            dst.rpc("insert_master_edge_with_evidence", {
                "p_edge": {k: edge[k] for k in (
                    "src_concept_id", "dst_concept_id", "relationship", "urgency", "tier",
                    "status", "candidate_origin", "extraction_run_id", "extraction_pass",
                    "prior_alpha", "prior_beta", "expected_prevalence_low",
                    "expected_prevalence_high", "patient_phrasing", "rejection_reason")},
                "p_evidence": [{
                    "source_section_id": r["source_section_id"],
                    "source_document_id": r["source_document_id"],
                    "section_ref": r["section_ref"],
                    "evidence_kind": r["evidence_kind"],
                    "quoted_sentence": r["quoted_sentence"],
                    "reasoning": r["reasoning"],
                    "char_offset": r["char_offset"],
                    "ordinal": i,
                } for i, r in enumerate(rows)],
            }).execute()
            moved += 1
            if moved % 10 == 0:
                print(f"    {moved} edges")
        except Exception as exc:  # noqa: BLE001
            # A citation that will not re-verify against the copied text is
            # exactly what this run exists to surface.
            failed.append((edge["id"], str(exc)[:150]))

    print("\n" + "=" * 62)
    print(f"edges copied        {moved}{'  (dry run)' if args.dry_run else ''}")
    print(f"already present     {skipped}")
    print(f"failed              {len(failed)}")
    for eid, why in failed[:10]:
        print(f"  {eid[:8]}: {why}")

    if not args.dry_run:
        print("\nverifying prod:")
        for table in ("concept", "source_document", "source_section",
                      "master_edge", "master_edge_evidence"):
            n = dst.table(table).select("id", count="exact").limit(1).execute().count
            print(f"  {table:22} {n}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
