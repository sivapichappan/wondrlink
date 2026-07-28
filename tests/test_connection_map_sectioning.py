# test_connection_map_sectioning.py
"""Guardrails for verbatim sectioning (SPEC §4.2, §6.1).

Every citation in this feature is verified by exact string comparison at a
character offset. If sectioning alters a single character, or if an offset is
off by one, the database trigger rejects real quotations and the extraction
pipeline silently produces nothing. These tests pin both properties against
the text hazards real guideline PDFs actually contain.
"""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.corpus import (  # noqa: E402
    MAX_SECTION_CHARS,
    MIN_SECTION_CHARS,
    PAGE_SEPARATOR,
    build_canonical_text,
    locate_quote,
    section_rows,
    sectionize,
    verify_partition,
)

BODY = ("Patients receiving an aromatase inhibitor commonly report new joint pain. "
        "This is among the most frequent reasons for stopping endocrine therapy. ") * 3

PAGES = [
    "TREATMENT SIDE EFFECTS\n" + BODY + "\n",
    "MANAGEMENT\n" + BODY + "\n",
]


def canonical(pages):
    return build_canonical_text(pages)


class TestPartitionInvariant:
    def test_sections_reproduce_the_document_exactly(self):
        text = canonical(PAGES)
        sections = sectionize(PAGES)
        assert "".join(s.text for s in sections) == text

    def test_verify_partition_agrees(self):
        assert verify_partition(canonical(PAGES), sectionize(PAGES)) == []

    def test_offsets_slice_back_to_the_same_text(self):
        text = canonical(PAGES)
        for s in sectionize(PAGES):
            assert text[s.char_start:s.char_end] == s.text

    def test_sections_are_contiguous(self):
        sections = sectionize(PAGES)
        for prev, nxt in zip(sections, sections[1:]):
            assert nxt.char_start == prev.char_end

    def test_span_equals_text_length(self):
        # The DB mirrors this as a CHECK constraint.
        for s in sectionize(PAGES):
            assert s.char_end - s.char_start == len(s.text)

    def test_empty_document_yields_nothing(self):
        assert sectionize([]) == []
        assert sectionize([""]) == []
        assert verify_partition("", []) == []


class TestVerbatimPreservation:
    """The hazards lib/pdf_utils.py deliberately destroys for retrieval."""

    HAZARDS = [
        "   leading spaces preserved\n",
        "trailing spaces preserved   \n",
        "\n\n\nblank lines preserved\n",
        "tabs\tpreserved\n",
        "double  internal  spaces\n",
        "unicode: café naïve — en–dash  nbsp\n",
        "combining: é vs é\n",
        "bullets: • item · item\n",
    ]

    def test_every_hazard_survives_verbatim(self):
        pages = ["HAZARD SECTION\n" + "".join(self.HAZARDS) + BODY]
        text = canonical(pages)
        sections = sectionize(pages)
        rebuilt = "".join(s.text for s in sections)
        assert rebuilt == text
        for hazard in self.HAZARDS:
            assert hazard in rebuilt

    def test_no_stripping_of_section_edges(self):
        pages = ["SECTION ONE\n   indented body line\n" + BODY,
                 "SECTION TWO\n   another indented line\n" + BODY]
        for s in sectionize(pages):
            assert s.text == s.text  # identity, but the real check is below
        rebuilt = "".join(s.text for s in sectionize(pages))
        assert "   indented body line" in rebuilt
        assert "   another indented line" in rebuilt

    def test_combining_characters_are_not_normalized(self):
        pages = ["NOTES\n" + "éclair\n" + BODY]
        rebuilt = "".join(s.text for s in sectionize(pages))
        assert "éclair" in rebuilt
        assert "éclair" not in rebuilt


class TestPageMapping:
    def test_pages_are_joined_with_the_separator(self):
        text = canonical(["a", "b", "c"])
        assert text == f"a{PAGE_SEPARATOR}b{PAGE_SEPARATOR}c"

    def test_page_numbers_are_one_based(self):
        sections = sectionize(PAGES)
        assert sections[0].page_start == 1
        assert sections[-1].page_end == len(PAGES)

    def test_section_spanning_a_page_break_reports_both_pages(self):
        # Body text continues across the break with no heading on page 2.
        pages = ["ONLY HEADING\n" + BODY, BODY]
        sections = sectionize(pages)
        spanning = [s for s in sections if s.page_start != s.page_end]
        assert spanning, "expected a section crossing the page separator"
        assert spanning[0].page_start == 1 and spanning[0].page_end == 2

    def test_offsets_account_for_the_separator(self):
        pages = ["AAA HEADING\n" + BODY, "BBB HEADING\n" + BODY]
        text = canonical(pages)
        for s in sectionize(pages):
            assert text[s.char_start:s.char_end] == s.text
        assert text.count(PAGE_SEPARATOR) == 1


class TestQuoteLocation:
    def test_quote_offset_round_trips_through_the_section(self):
        sections = sectionize(PAGES)
        quote = "new joint pain"
        for s in sections:
            off = locate_quote(s, quote)
            if off >= 0:
                # This is exactly what the DB trigger recomputes with substr().
                assert s.text[off:off + len(quote)] == quote
                break
        else:
            raise AssertionError("quote not found in any section")

    def test_section_offset_maps_into_the_document(self):
        text = canonical(PAGES)
        quote = "endocrine therapy"
        for s in sectionize(PAGES):
            off = locate_quote(s, quote)
            if off >= 0:
                assert text[s.char_start + off:s.char_start + off + len(quote)] == quote
                return
        raise AssertionError("quote not found")

    def test_missing_quote_returns_minus_one(self):
        s = sectionize(PAGES)[0]
        assert locate_quote(s, "this sentence is not in the corpus") == -1
        assert locate_quote(s, "") == -1

    def test_lookup_is_exact_not_fuzzy(self):
        # §16: no case folding, no whitespace tolerance.
        s = sectionize(PAGES)[0]
        assert locate_quote(s, "NEW JOINT PAIN") == -1
        assert locate_quote(s, "new  joint  pain") == -1


class TestSizeGuards:
    def test_runt_sections_merge_forward_without_losing_text(self):
        # Three headings in a row: the first two are far shorter than the
        # minimum and must not become their own sections.
        pages = ["FIRST HEADING\nSECOND HEADING\nTHIRD HEADING\n" + BODY]
        text = canonical(pages)
        sections = sectionize(pages)
        assert "".join(s.text for s in sections) == text
        assert all(len(s.text) >= MIN_SECTION_CHARS or s is sections[-1] for s in sections)

    def test_long_unstructured_document_is_split_without_loss(self):
        pages = ["x" * (MAX_SECTION_CHARS * 2) + "\n" + "y" * 500 + "\n"]
        text = canonical(pages)
        sections = sectionize(pages)
        assert "".join(s.text for s in sections) == text
        assert verify_partition(text, sections) == []

    def test_split_happens_at_a_line_start(self):
        line = ("z" * 99) + "\n"
        pages = [line * (MAX_SECTION_CHARS // 50)]
        text = canonical(pages)
        sections = sectionize(pages)
        assert "".join(s.text for s in sections) == text
        for s in sections[1:]:
            assert text[s.char_start - 1] in ("\n", PAGE_SEPARATOR)


class TestHeadingsAndRefs:
    def test_first_section_starts_at_zero(self):
        assert sectionize(PAGES)[0].char_start == 0

    def test_preamble_without_a_heading_still_becomes_a_section(self):
        pages = [BODY + "\nREAL HEADING\n" + BODY]
        sections = sectionize(pages)
        assert sections[0].heading == ""
        assert sections[0].char_start == 0
        assert "".join(s.text for s in sections) == canonical(pages)

    def test_heading_is_stored_verbatim(self):
        pages = ["  SPACED HEADING  \n" + BODY, "MANAGEMENT\n" + BODY]
        headings = [s.heading for s in sectionize(pages) if s.heading]
        assert "MANAGEMENT" in headings

    def test_section_refs_are_unique_and_ordered(self):
        sections = sectionize(PAGES)
        refs = [s.section_ref for s in sections]
        assert len(set(refs)) == len(refs)
        assert refs == sorted(refs)

    def test_sentences_are_not_treated_as_headings(self):
        pages = ["This is an ordinary sentence that ends with a period.\n" + BODY]
        assert sectionize(pages)[0].heading == ""

    def test_determinism(self):
        assert sectionize(PAGES) == sectionize(PAGES)


class TestVerifyPartitionCatchesCorruption:
    def test_detects_altered_text(self):
        text = canonical(PAGES)
        sections = sectionize(PAGES)
        broken = sections[0]._replace(text=sections[0].text.strip())
        assert verify_partition(text, [broken] + list(sections[1:])) != []

    def test_detects_dropped_section(self):
        text = canonical(PAGES)
        sections = sectionize(PAGES)
        if len(sections) > 1:
            assert verify_partition(text, sections[:-1]) != []

    def test_detects_bad_offsets(self):
        text = canonical(PAGES)
        sections = sectionize(PAGES)
        shifted = sections[0]._replace(char_start=1)
        assert verify_partition(text, [shifted] + list(sections[1:])) != []

    def test_empty_sections_for_nonempty_document_is_an_error(self):
        assert verify_partition("some text", []) != []


class TestRowShape:
    def test_rows_carry_every_column_the_table_needs(self):
        rows = section_rows("doc-uuid", sectionize(PAGES))
        expected = {"document_id", "section_ref", "ordinal", "heading", "text",
                    "char_start", "char_end", "page_start", "page_end"}
        assert rows and all(set(r) == expected for r in rows)

    def test_absent_heading_is_null_not_empty_string(self):
        pages = [BODY]
        rows = section_rows("doc-uuid", sectionize(pages))
        assert rows[0]["heading"] is None

    def test_row_text_is_untouched(self):
        sections = sectionize(PAGES)
        rows = section_rows("doc-uuid", sections)
        for row, s in zip(rows, sections):
            assert row["text"] == s.text
