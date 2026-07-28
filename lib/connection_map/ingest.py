"""Corpus ingest orchestration (SPEC-connection-map.md §4.2).

The PDF reading and the Supabase client both live in the script
(scripts/ingest_connection_map_corpus.py); everything decidable without them
lives here so it can be tested offline. The store is a narrow adapter rather
than a raw Supabase client so tests can substitute a fake without mocking
PostgREST's builder chain.

The one rule this module exists to enforce: text goes into the database
exactly as it came out of the PDF, and that is verified twice — once before
insert and once by reading the rows back afterwards. A citation checked
against text that was altered in transit is worse than no citation at all.
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from connection_map.corpus import (
    build_canonical_text,
    section_rows,
    sectionize,
    verify_partition,
)

MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "connection_map" / "corpus_manifest.yaml"
)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

_REQUIRED_KEYS = {"file", "title", "scope"}
_ALLOWED_KEYS = _REQUIRED_KEYS | {"publisher", "edition", "cancer", "notes"}

SCOPES = ("cancer_specific", "general_survivorship")

SECTION_BATCH = 100


class IngestError(Exception):
    """Raised when a document cannot be ingested safely. Aborts that document
    only; the run continues with the next one."""


def load_manifest(path: Path = MANIFEST_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise ValueError("corpus manifest must be a YAML mapping")
    return doc


def validate_manifest(doc: Dict[str, Any], data_dir: Path = DATA_DIR) -> List[str]:
    """Returns error strings; empty means valid. Never raises."""
    errors: List[str] = []
    documents = doc.get("documents")
    if not isinstance(documents, list) or not documents:
        return ["manifest 'documents' must be a non-empty list"]

    seen: set = set()
    for i, entry in enumerate(documents):
        where = f"documents[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where}: not a mapping")
            continue

        name = entry.get("file")
        label = name if isinstance(name, str) and name else where

        missing = _REQUIRED_KEYS - set(entry)
        if missing:
            errors.append(f"{label}: missing required keys {sorted(missing)}")
        unknown = set(entry) - _ALLOWED_KEYS
        if unknown:
            errors.append(f"{label}: unknown keys {sorted(unknown)}")

        if not isinstance(name, str) or not name:
            errors.append(f"{where}: 'file' must be a non-empty string")
        else:
            if name in seen:
                errors.append(f"{label}: duplicate file entry")
            seen.add(name)
            if data_dir is not None and not (data_dir / name).exists():
                errors.append(f"{label}: file not found in {data_dir}")

        title = entry.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{label}: 'title' must be a non-empty string")

        scope = entry.get("scope")
        if scope not in SCOPES:
            errors.append(f"{label}: scope {scope!r} not in {SCOPES}")
        else:
            # Mirrors the source_document CHECK constraint: a cancer-specific
            # document names its cancer, a general one must not.
            cancer = entry.get("cancer")
            if scope == "cancer_specific" and not cancer:
                errors.append(f"{label}: cancer_specific documents must name a cancer")
            if scope == "general_survivorship" and cancer:
                errors.append(f"{label}: general_survivorship documents must not name a cancer")

    return errors


def canonical_sha256(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def document_row(entry: Dict[str, Any], sha: str) -> Dict[str, Any]:
    return {
        "title": entry["title"],
        "publisher": entry.get("publisher"),
        "edition": entry.get("edition"),
        "scope": entry["scope"],
        "cancer": entry.get("cancer"),
        "file_path": f"data/{entry['file']}",
        "content_sha256": sha,
    }


class CorpusStore:
    """Narrow adapter over the Supabase client. Tests use a fake with the
    same five methods."""

    def __init__(self, client: Any):
        self._client = client

    def find_document(self, file_path: str) -> Optional[Dict[str, Any]]:
        res = (self._client.table("source_document")
               .select("id, content_sha256")
               .eq("file_path", file_path)
               .execute())
        rows = res.data or []
        return rows[0] if rows else None

    def count_sections(self, document_id: str) -> int:
        res = (self._client.table("source_section")
               .select("id", count="exact")
               .eq("document_id", document_id)
               .execute())
        return res.count or 0

    def upsert_document(self, row: Dict[str, Any]) -> str:
        res = (self._client.table("source_document")
               .upsert(row, on_conflict="file_path")
               .execute())
        return (res.data or [{}])[0].get("id")

    def count_citations(self, document_id: str) -> int:
        res = (self._client.table("master_edge_evidence")
               .select("id", count="exact")
               .eq("source_document_id", document_id)
               .execute())
        return res.count or 0

    def set_content_sha(self, document_id: str, sha: str) -> None:
        (self._client.table("source_document")
         .update({"content_sha256": sha})
         .eq("id", document_id)
         .execute())

    def delete_sections(self, document_id: str) -> None:
        (self._client.table("source_section")
         .delete()
         .eq("document_id", document_id)
         .execute())

    def insert_sections(self, rows: Sequence[Dict[str, Any]]) -> None:
        for i in range(0, len(rows), SECTION_BATCH):
            (self._client.table("source_section")
             .insert(list(rows[i:i + SECTION_BATCH]))
             .execute())

    def fetch_sections(self, document_id: str) -> List[Dict[str, Any]]:
        res = (self._client.table("source_section")
               .select("ordinal, text, char_start, char_end")
               .eq("document_id", document_id)
               .order("ordinal")
               .execute())
        return res.data or []


def ingest_document(
    store: CorpusStore,
    entry: Dict[str, Any],
    page_texts: Sequence[str],
    force: bool = False,
) -> Dict[str, Any]:
    """Ingest one document. Returns a result dict; raises IngestError when the
    document cannot be stored safely."""
    canonical = build_canonical_text(page_texts)
    if not canonical.strip():
        raise IngestError("no text extracted")

    # Postgres TEXT cannot hold a NUL. Substituting one would break the
    # verbatim guarantee, so this is a hard stop for the document rather than
    # something to clean up.
    if "\x00" in canonical:
        raise IngestError("extracted text contains a NUL byte; cannot store verbatim")

    sha = canonical_sha256(canonical)
    file_path = f"data/{entry['file']}"
    existing = store.find_document(file_path)

    if existing and not force:
        if existing.get("content_sha256") == sha and store.count_sections(existing["id"]) > 0:
            return {"file": entry["file"], "status": "skipped", "sections": 0}

    sections = sectionize(page_texts)
    errors = verify_partition(canonical, sections)
    if errors:
        raise IngestError(f"sectioning failed verification: {errors[0]}")

    # Refuse before touching anything if this document is already cited. The
    # evidence FK (ON DELETE RESTRICT) would block the section delete anyway,
    # but failing here leaves the existing row completely untouched. Re-ingesting
    # a cited document is a governance action, not something --force papers over.
    if existing:
        cited = store.count_citations(existing["id"])
        if cited:
            raise IngestError(
                f"{cited} citation(s) reference this document; re-ingesting would "
                "invalidate them (governance action, not a --force flag)")

    # The hash is written LAST, and cleared first. Each PostgREST call is its
    # own transaction, so a hash committed up front would still be there if the
    # section write failed afterwards — and the skip-if-unchanged check above
    # would then report the document as "unchanged" on every later run, turning
    # a loud failure into permanent silent drift from data/. A null hash means
    # "sections not verified", which re-ingests instead.
    document_id = store.upsert_document(document_row(entry, None)) or (
        existing or {}).get("id")
    if not document_id:
        raise IngestError("could not resolve document id after upsert")

    store.delete_sections(document_id)
    store.insert_sections(section_rows(document_id, sections))

    stored = store.fetch_sections(document_id)
    round_trip = verify_round_trip(canonical, stored)
    if round_trip:
        raise IngestError(f"stored text does not match source: {round_trip[0]}")

    store.set_content_sha(document_id, sha)
    return {"file": entry["file"], "status": "ingested", "sections": len(sections)}


def verify_round_trip(canonical: str, stored_rows: Sequence[Dict[str, Any]]) -> List[str]:
    """Confirm what the database now holds still reproduces the source exactly.

    Cheap, and it is the difference between discovering a transport problem now
    versus discovering it when a physician rejects a citation that was actually
    correct.
    """
    errors: List[str] = []
    if not stored_rows:
        return ["no sections were stored"]

    rows = sorted(stored_rows, key=lambda r: r["ordinal"])
    if "".join(r["text"] for r in rows) != canonical:
        errors.append("stored sections do not concatenate to the source text")
    for r in rows:
        if canonical[r["char_start"]:r["char_end"]] != r["text"]:
            errors.append(f"section {r['ordinal']}: stored offsets do not match stored text")
            break
    return errors
