# test_connection_map_ingest.py
"""Guardrails for corpus ingest (SPEC §4.2).

Covers the manifest contract and the ingest orchestration against a fake
store, so no PDF and no database are needed. What matters here: a document is
never stored with altered text, an unchanged document is not re-written, and
verification runs on both sides of the write.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.ingest import (  # noqa: E402
    MANIFEST_PATH,
    CorpusStore,
    IngestError,
    canonical_sha256,
    document_row,
    ingest_document,
    load_manifest,
    validate_manifest,
    verify_round_trip,
)
from connection_map.corpus import build_canonical_text  # noqa: E402

BODY = ("Joint pain is reported by patients taking an aromatase inhibitor. "
        "Fatigue and poor sleep frequently occur together. ") * 4

PAGES = ["TREATMENT\n" + BODY, "MANAGEMENT\n" + BODY]


class FakeStore(CorpusStore):
    """Same methods as the real adapter, backed by dicts."""

    def __init__(self, existing=None, sections=0, citations=0):
        self._existing = existing
        self._section_count = sections
        self._citations = citations
        self.rows = []
        self.calls = []
        self.sha = (existing or {}).get("content_sha256")

    def find_document(self, file_path):
        self.calls.append(("find", file_path))
        return self._existing

    def count_sections(self, document_id):
        self.calls.append(("count", document_id))
        return self._section_count

    def count_citations(self, document_id):
        self.calls.append(("citations", document_id))
        return self._citations

    def set_content_sha(self, document_id, sha):
        self.calls.append(("set_sha", sha))
        self.sha = sha

    def upsert_document(self, row):
        self.calls.append(("upsert", row["file_path"]))
        self.sha = row["content_sha256"]
        return "doc-1"

    def delete_sections(self, document_id):
        self.calls.append(("delete", document_id))
        self.rows = []

    def insert_sections(self, rows):
        self.calls.append(("insert", len(rows)))
        self.rows.extend(rows)

    def fetch_sections(self, document_id):
        self.calls.append(("fetch", document_id))
        return [{"ordinal": r["ordinal"], "text": r["text"],
                 "char_start": r["char_start"], "char_end": r["char_end"]}
                for r in self.rows]


ENTRY = {"file": "breast-invasive-patient.pdf", "title": "T",
         "scope": "cancer_specific", "cancer": "breast"}


class TestShippedManifest:
    @pytest.fixture(scope="class")
    def manifest(self):
        return load_manifest(MANIFEST_PATH)

    def test_validates_against_the_real_data_directory(self, manifest):
        assert validate_manifest(manifest) == []

    def test_contains_both_scopes(self, manifest):
        scopes = {d["scope"] for d in manifest["documents"]}
        # §4.2: a breast-only corpus underproduces symptom-cluster candidates.
        assert scopes == {"cancer_specific", "general_survivorship"}

    def test_every_cancer_specific_entry_is_breast(self, manifest):
        for d in manifest["documents"]:
            if d["scope"] == "cancer_specific":
                assert d["cancer"] == "breast", d["file"]

    def test_file_names_are_unique(self, manifest):
        names = [d["file"] for d in manifest["documents"]]
        assert len(set(names)) == len(names)


class TestManifestValidation:
    def _entry(self, **over):
        base = {"file": "breast-invasive-patient.pdf", "title": "Title",
                "publisher": "NCCN", "edition": None,
                "scope": "cancer_specific", "cancer": "breast"}
        base.update(over)
        return {"version": 1, "documents": [base]}

    def test_accepts_valid_entry(self):
        assert validate_manifest(self._entry()) == []

    def test_rejects_missing_file(self):
        errors = validate_manifest(self._entry(file="does-not-exist.pdf"))
        assert any("file not found" in e for e in errors)

    def test_rejects_cancer_specific_without_cancer(self):
        errors = validate_manifest(self._entry(cancer=None))
        assert any("must name a cancer" in e for e in errors)

    def test_rejects_general_with_cancer(self):
        errors = validate_manifest(self._entry(
            file="ACS_Caregiver_Support.pdf",
            scope="general_survivorship", cancer="breast"))
        assert any("must not name a cancer" in e for e in errors)

    def test_rejects_unknown_scope(self):
        errors = validate_manifest(self._entry(scope="clinical_trial"))
        assert any("scope" in e for e in errors)

    def test_rejects_empty_title(self):
        errors = validate_manifest(self._entry(title="  "))
        assert any("title" in e for e in errors)

    def test_rejects_unknown_key(self):
        doc = self._entry()
        doc["documents"][0]["cancer_types"] = ["breast"]
        assert any("unknown keys" in e for e in validate_manifest(doc))

    def test_rejects_duplicate_file(self):
        doc = self._entry()
        doc["documents"].append(dict(doc["documents"][0]))
        assert any("duplicate" in e for e in validate_manifest(doc))

    def test_rejects_empty_document_list(self):
        assert validate_manifest({"version": 1, "documents": []}) != []


class TestDocumentRow:
    def test_file_path_is_repo_relative(self):
        row = document_row(ENTRY, "abc")
        assert row["file_path"] == "data/breast-invasive-patient.pdf"

    def test_hash_travels_with_the_row(self):
        assert document_row(ENTRY, "abc")["content_sha256"] == "abc"

    def test_hash_changes_with_content(self):
        a = canonical_sha256(build_canonical_text(PAGES))
        b = canonical_sha256(build_canonical_text(PAGES + ["extra"]))
        assert a != b

    def test_hash_is_whitespace_sensitive(self):
        # Verbatim means a stray space is a different document.
        assert canonical_sha256("a b") != canonical_sha256("a  b")


class TestIngestDocument:
    def test_happy_path_writes_and_verifies(self):
        store = FakeStore()
        result = ingest_document(store, ENTRY, PAGES)
        assert result["status"] == "ingested"
        assert result["sections"] > 0
        kinds = [c[0] for c in store.calls]
        # Delete before insert, and read back after.
        assert kinds.index("delete") < kinds.index("insert") < kinds.index("fetch")

    def test_stored_text_reproduces_the_source(self):
        store = FakeStore()
        ingest_document(store, ENTRY, PAGES)
        assert "".join(r["text"] for r in store.rows) == build_canonical_text(PAGES)

    def test_unchanged_document_is_skipped(self):
        sha = canonical_sha256(build_canonical_text(PAGES))
        store = FakeStore(existing={"id": "doc-1", "content_sha256": sha}, sections=5)
        result = ingest_document(store, ENTRY, PAGES)
        assert result["status"] == "skipped"
        assert not any(c[0] in ("delete", "insert") for c in store.calls)

    def test_force_reingests_unchanged_document(self):
        sha = canonical_sha256(build_canonical_text(PAGES))
        store = FakeStore(existing={"id": "doc-1", "content_sha256": sha}, sections=5)
        result = ingest_document(store, ENTRY, PAGES, force=True)
        assert result["status"] == "ingested"
        assert any(c[0] == "insert" for c in store.calls)

    def test_changed_content_reingests_without_force(self):
        store = FakeStore(existing={"id": "doc-1", "content_sha256": "stale"}, sections=5)
        assert ingest_document(store, ENTRY, PAGES)["status"] == "ingested"

    def test_existing_document_with_no_sections_reingests(self):
        sha = canonical_sha256(build_canonical_text(PAGES))
        store = FakeStore(existing={"id": "doc-1", "content_sha256": sha}, sections=0)
        assert ingest_document(store, ENTRY, PAGES)["status"] == "ingested"

    def test_nul_byte_is_a_hard_stop(self):
        store = FakeStore()
        with pytest.raises(IngestError, match="NUL"):
            ingest_document(store, ENTRY, ["HEADING\n" + BODY + "\x00tail"])
        assert not store.rows

    def test_empty_extraction_is_a_hard_stop(self):
        store = FakeStore()
        with pytest.raises(IngestError, match="no text"):
            ingest_document(store, ENTRY, ["", "   "])
        assert not store.rows

    def test_round_trip_mismatch_raises(self):
        class Corrupting(FakeStore):
            def fetch_sections(self, document_id):
                rows = super().fetch_sections(document_id)
                rows[0]["text"] = rows[0]["text"].strip()  # a "helpful" cleanup
                return rows

        with pytest.raises(IngestError, match="does not match source"):
            ingest_document(Corrupting(), ENTRY, PAGES)


class TestFailureIsNotSilentlyMasked:
    """Each PostgREST call is its own transaction. If the content hash were
    written before the sections it describes, a failure in between would leave
    a document row advertising text the section rows do not hold — and the
    skip-if-unchanged check would then report it as unchanged forever, so the
    corpus would drift from data/ with no signal."""

    def test_hash_is_written_only_after_verification(self):
        store = FakeStore()
        ingest_document(store, ENTRY, PAGES)
        kinds = [c[0] for c in store.calls]
        assert kinds.index("set_sha") > kinds.index("fetch")
        assert store.sha == canonical_sha256(build_canonical_text(PAGES))

    def test_upsert_does_not_carry_the_hash(self):
        store = FakeStore()
        ingest_document(store, ENTRY, PAGES)
        assert document_row(ENTRY, None)["content_sha256"] is None
        # The hash the row ends with came from set_content_sha, not the upsert.
        assert [c for c in store.calls if c[0] == "set_sha"]

    def test_failed_write_leaves_no_hash_so_the_next_run_retries(self):
        class FailsOnInsert(FakeStore):
            def insert_sections(self, rows):
                raise RuntimeError("network died mid-batch")

        store = FailsOnInsert()
        with pytest.raises(RuntimeError):
            ingest_document(store, ENTRY, PAGES)
        assert store.sha is None, "a failed ingest must not leave a hash behind"

    def test_failed_verification_leaves_no_hash(self):
        class Corrupting(FakeStore):
            def fetch_sections(self, document_id):
                rows = super().fetch_sections(document_id)
                rows[0]["text"] = rows[0]["text"].strip()
                return rows

        store = Corrupting()
        with pytest.raises(IngestError):
            ingest_document(store, ENTRY, PAGES)
        assert store.sha is None

    def test_document_with_no_hash_is_never_skipped(self):
        store = FakeStore(existing={"id": "doc-1", "content_sha256": None}, sections=5)
        assert ingest_document(store, ENTRY, PAGES)["status"] == "ingested"

    def test_cited_document_refuses_before_touching_anything(self):
        sha = canonical_sha256(build_canonical_text(PAGES))
        store = FakeStore(existing={"id": "doc-1", "content_sha256": "stale"},
                          sections=5, citations=3)
        with pytest.raises(IngestError, match="citation"):
            ingest_document(store, ENTRY, PAGES)
        # Nothing was written, so the existing row keeps describing what it holds.
        assert store.sha == "stale" != sha
        assert not any(c[0] in ("upsert", "delete", "insert") for c in store.calls)

    def test_force_does_not_override_citations(self):
        store = FakeStore(existing={"id": "doc-1", "content_sha256": "stale"},
                          sections=5, citations=1)
        with pytest.raises(IngestError, match="governance"):
            ingest_document(store, ENTRY, PAGES, force=True)

    def test_multi_section_document_writes_every_section(self):
        store = FakeStore()
        big = ["HEADING %d\n%s" % (i, BODY) for i in range(120)]
        result = ingest_document(store, ENTRY, big)
        assert result["sections"] == len(store.rows) > 100
        assert "".join(r["text"] for r in store.rows) == build_canonical_text(big)


class TestCorpusStoreBatching:
    """FakeStore replaces insert_sections, so batching is verified here, on
    the real adapter, with the Supabase client mocked."""

    def test_inserts_are_chunked(self):
        client = MagicMock()
        store = CorpusStore(client)
        rows = [{"ordinal": i, "text": "x"} for i in range(250)]
        store.insert_sections(rows)
        calls = client.table.return_value.insert.call_args_list
        assert [len(c.args[0]) for c in calls] == [100, 100, 50]
        assert sum(len(c.args[0]) for c in calls) == 250

    def test_single_batch_when_small(self):
        client = MagicMock()
        CorpusStore(client).insert_sections([{"ordinal": 0}])
        assert client.table.return_value.insert.call_count == 1

    def test_empty_rows_write_nothing(self):
        client = MagicMock()
        CorpusStore(client).insert_sections([])
        assert client.table.return_value.insert.call_count == 0


class TestRoundTripVerification:
    def test_accepts_faithful_rows(self):
        canonical = "abcdef"
        rows = [{"ordinal": 0, "text": "abc", "char_start": 0, "char_end": 3},
                {"ordinal": 1, "text": "def", "char_start": 3, "char_end": 6}]
        assert verify_round_trip(canonical, rows) == []

    def test_rejects_missing_rows(self):
        assert verify_round_trip("abc", []) != []

    def test_rejects_altered_text(self):
        rows = [{"ordinal": 0, "text": "abX", "char_start": 0, "char_end": 3}]
        assert verify_round_trip("abc", rows) != []

    def test_rejects_bad_offsets(self):
        rows = [{"ordinal": 0, "text": "abc", "char_start": 1, "char_end": 4}]
        assert verify_round_trip("abc", rows) != []

    def test_sorts_by_ordinal_before_comparing(self):
        rows = [{"ordinal": 1, "text": "def", "char_start": 3, "char_end": 6},
                {"ordinal": 0, "text": "abc", "char_start": 0, "char_end": 3}]
        assert verify_round_trip("abcdef", rows) == []
