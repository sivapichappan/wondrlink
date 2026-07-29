# test_connection_map_extraction.py
"""Extraction validation (SPEC §6.1, §6.2; acceptance #11, #12).

The single most important test in this file is that a quotation which is not
an EXACT substring of its section is rejected. The characteristic failure of
this pipeline is a plausible relationship carrying an invented citation, and
exact matching is the only thing that catches it every time.

Offline: no model, no database. The validators are pure by design so these
rules can be proven without either.
"""

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.extraction.repair import (  # noqa: E402
    anchor_quote,
    normalised_equal,
)
from connection_map.extraction.validate import (  # noqa: E402
    MIN_PASS2_EVIDENCE,
    find_exact_quote,
    parse_model_json,
    rejection_summary,
    validate_pass1,
    validate_pass2,
)

SECTION = (
    "Joint pain is common with an aromatase inhibitor. "
    "It is a leading reason women stop endocrine therapy early.\n"
    "Some patients report  double  spaced text and a trailing space. "
)

SLUGS = {"joint_pain", "aromatase_inhibitor", "medication_adherence", "fatigue"}
RELS = {"side_effect_of", "co_occurs_with", "indicated_by"}


def one(**over):
    base = {
        "src_concept_slug": "joint_pain",
        "dst_concept_slug": "aromatase_inhibitor",
        "relationship": "side_effect_of",
        "quoted_sentence": "Joint pain is common with an aromatase inhibitor.",
    }
    base.update(over)
    return {"candidates": [base]}


class TestExactCitation:
    """Acceptance #11, and §16's do-not-soften rule."""

    def test_exact_quote_is_accepted(self):
        ok, bad = validate_pass1(one(), SECTION, SLUGS, RELS)
        assert len(ok) == 1 and not bad
        assert ok[0]["char_offset"] == 0

    def test_offset_points_at_the_quote(self):
        ok, _ = validate_pass1(
            one(quoted_sentence="a leading reason women stop endocrine therapy"),
            SECTION, SLUGS, RELS)
        off = ok[0]["char_offset"]
        assert SECTION[off:off + len(ok[0]["quoted_sentence"])] == ok[0]["quoted_sentence"]

    def test_a_shorter_true_substring_is_still_a_real_citation(self):
        # Quoting a fragment that genuinely appears verbatim is legitimate —
        # the rule is "exact substring", not "exact whole sentence". Dropping
        # the trailing period leaves a string that IS in the source, so it is
        # accepted, and the stored offset still points at real text.
        quote = "Joint pain is common with an aromatase inhibitor"
        ok, bad = validate_pass1(one(quoted_sentence=quote), SECTION, SLUGS, RELS)
        assert len(ok) == 1 and not bad
        off = ok[0]["char_offset"]
        assert SECTION[off:off + len(quote)] == quote

    @pytest.mark.parametrize("quote,why", [
        ("Joint pain is common with the aromatase inhibitor.", "a word changed"),
        ("Joint pain is common.",                              "sentence shortened"),
        ("Joint pain is common with an aromatase inhibitor, which patients dislike.",
         "clause appended"),
        ("Patients taking aromatase inhibitors often get sore joints.", "paraphrased"),
        ("Aromatase inhibitors are safe and well tolerated.",  "wholly invented"),
    ])
    def test_an_altered_or_invented_sentence_is_still_rejected(self, quote, why):
        # Re-anchoring bridges MECHANICAL differences only. A sentence the
        # document does not contain is the case this pipeline exists to catch.
        ok, bad = validate_pass1(one(quoted_sentence=quote), SECTION, SLUGS, RELS)
        assert not ok, why
        assert bad[0]["reason"] == "quote_not_found"

    def test_find_exact_quote_never_normalises(self):
        assert find_exact_quote(SECTION, "double  spaced") >= 0
        assert find_exact_quote(SECTION, "double spaced") == -1
        assert find_exact_quote(SECTION, "") == -1
        assert find_exact_quote("", "anything") == -1


class TestPass1Vocabulary:
    def test_unknown_concept_is_rejected(self):
        ok, bad = validate_pass1(one(src_concept_slug="invented_concept"),
                                 SECTION, SLUGS, RELS)
        assert not ok and bad[0]["reason"] == "unknown_concept"

    def test_unknown_relationship_is_rejected(self):
        ok, bad = validate_pass1(one(relationship="cures"), SECTION, SLUGS, RELS)
        assert not ok and bad[0]["reason"] == "unknown_relationship"

    def test_self_loop_is_rejected(self):
        ok, bad = validate_pass1(one(dst_concept_slug="joint_pain"), SECTION, SLUGS, RELS)
        assert not ok and bad[0]["reason"] == "self_loop"

    def test_duplicate_within_a_batch_is_rejected_once(self):
        payload = one()
        payload["candidates"].append(dict(payload["candidates"][0]))
        ok, bad = validate_pass1(payload, SECTION, SLUGS, RELS)
        assert len(ok) == 1
        assert [r["reason"] for r in bad] == ["duplicate_in_batch"]

    def test_existing_triple_is_not_re_proposed(self):
        ok, bad = validate_pass1(
            one(), SECTION, SLUGS, RELS,
            existing_triples=[("joint_pain", "aromatase_inhibitor", "side_effect_of")])
        assert not ok and bad[0]["reason"] == "already_exists"

    def test_empty_and_malformed_candidates(self):
        ok, bad = validate_pass1({"candidates": [
            "not an object", {}, {"src_concept_slug": "joint_pain"},
            dict(one()["candidates"][0], quoted_sentence="   "),
        ]}, SECTION, SLUGS, RELS)
        assert not ok
        assert {r["reason"] for r in bad} == {"malformed", "empty_quote"}

    def test_empty_output_is_normal(self):
        assert validate_pass1({"candidates": []}, SECTION, SLUGS, RELS) == ([], [])
        assert validate_pass1(None, SECTION, SLUGS, RELS) == ([], [])

    def test_accepted_candidates_are_tier_a_pass_1(self):
        ok, _ = validate_pass1(one(), SECTION, SLUGS, RELS)
        assert ok[0]["tier"] == "A" and ok[0]["extraction_pass"] == 1


class TestPass2Chaining:
    """Acceptance #12: fewer than two verified quotations is not a chain."""

    IDS = ["ev-1", "ev-2", "ev-3"]

    def chain(self, **over):
        base = {
            "src_concept_slug": "joint_pain",
            "dst_concept_slug": "medication_adherence",
            "relationship": "co_occurs_with",
            "evidence_ids": ["ev-1", "ev-2"],
            "reasoning": "one says the symptom is common, the other that it stops treatment",
        }
        base.update(over)
        return {"candidates": [base]}

    def test_two_verified_quotations_are_accepted(self):
        ok, bad = validate_pass2(self.chain(), self.IDS, SLUGS, RELS)
        assert len(ok) == 1 and not bad
        assert ok[0]["tier"] == "B" and ok[0]["extraction_pass"] == 2

    def test_one_quotation_is_rejected(self):
        ok, bad = validate_pass2(self.chain(evidence_ids=["ev-1"]), self.IDS, SLUGS, RELS)
        assert not ok and bad[0]["reason"] == "too_few_evidence"

    def test_no_quotations_is_rejected(self):
        ok, bad = validate_pass2(self.chain(evidence_ids=[]), self.IDS, SLUGS, RELS)
        assert not ok and bad[0]["reason"] == "too_few_evidence"

    def test_the_minimum_is_two(self):
        assert MIN_PASS2_EVIDENCE == 2

    def test_an_invented_evidence_id_is_rejected(self):
        # Pass 2 may never introduce a quotation; citing an id that does not
        # exist is the chaining form of an invented citation.
        ok, bad = validate_pass2(self.chain(evidence_ids=["ev-1", "ev-999"]),
                                 self.IDS, SLUGS, RELS)
        assert not ok and bad[0]["reason"] == "unknown_evidence"

    def test_citing_the_same_quotation_twice_is_not_two_sources(self):
        ok, bad = validate_pass2(self.chain(evidence_ids=["ev-1", "ev-1"]),
                                 self.IDS, SLUGS, RELS)
        assert not ok and bad[0]["reason"] == "duplicate_evidence"

    def test_vocabulary_rules_apply_here_too(self):
        for over, reason in (({"src_concept_slug": "nope"}, "unknown_concept"),
                             ({"relationship": "cures"}, "unknown_relationship"),
                             ({"dst_concept_slug": "joint_pain"}, "self_loop")):
            ok, bad = validate_pass2(self.chain(**over), self.IDS, SLUGS, RELS)
            assert not ok and bad[0]["reason"] == reason

    def test_existing_triple_is_not_re_proposed(self):
        ok, bad = validate_pass2(
            self.chain(), self.IDS, SLUGS, RELS,
            existing_triples=[("joint_pain", "medication_adherence", "co_occurs_with")])
        assert not ok and bad[0]["reason"] == "already_exists"


class TestEnvelopeTolerance:
    """Lenient about how the model wraps its answer, strict about contents."""

    def test_bare_list_is_accepted(self):
        ok, _ = validate_pass1(one()["candidates"], SECTION, SLUGS, RELS)
        assert len(ok) == 1

    def test_alternate_keys_are_accepted(self):
        ok, _ = validate_pass1({"relationships": one()["candidates"]},
                               SECTION, SLUGS, RELS)
        assert len(ok) == 1

    def test_json_in_a_code_fence(self):
        assert parse_model_json('```json\n{"candidates": []}\n```') == {"candidates": []}

    def test_json_with_surrounding_chatter(self):
        got = parse_model_json('Here you go:\n{"candidates": []}\nHope that helps.')
        assert got == {"candidates": []}

    def test_unparseable_returns_none(self):
        assert parse_model_json("not json at all") is None
        assert parse_model_json("") is None


class TestRejectionReporting:
    def test_counts_by_reason(self):
        _, bad = validate_pass1({"candidates": [
            dict(one()["candidates"][0], quoted_sentence="invented"),
            dict(one()["candidates"][0], quoted_sentence="also invented"),
            dict(one()["candidates"][0], src_concept_slug="nope"),
        ]}, SECTION, SLUGS, RELS)
        summary = rejection_summary(bad)
        assert summary["quote_not_found"] == 2
        assert summary["unknown_concept"] == 1

    def test_summary_is_ordered_by_frequency(self):
        _, bad = validate_pass1({"candidates": [
            dict(one()["candidates"][0], quoted_sentence="invented"),
            dict(one()["candidates"][0], quoted_sentence="also invented"),
            dict(one()["candidates"][0], src_concept_slug="nope"),
        ]}, SECTION, SLUGS, RELS)
        assert list(rejection_summary(bad))[0] == "quote_not_found"


class TestReAnchoring:
    """Owner decision D6: a near miss is re-anchored to the document's own
    words rather than discarded.

    The guarantee is unchanged — what gets STORED is always source text, so it
    still passes the exact check in the database trigger and again at
    publication. Only the way we FIND the sentence is tolerant.
    """

    def stored(self, quote):
        ok, bad = validate_pass1(one(quoted_sentence=quote), SECTION, SLUGS, RELS)
        return (ok[0] if ok else None), bad

    def test_case_difference_is_recovered(self):
        got, bad = self.stored("joint pain is common with an AROMATASE INHIBITOR.")
        assert got and not bad
        # The model's casing is discarded; the document's text is stored.
        assert got["quoted_sentence"] == "Joint pain is common with an aromatase inhibitor."
        assert got["quote_repaired"] is True

    def test_tidied_whitespace_is_recovered_with_the_originals_spacing(self):
        got, bad = self.stored("Some patients report double spaced text")
        assert got and not bad
        assert "double  spaced" in got["quoted_sentence"], "source spacing, not the model's"
        assert got["quote_repaired"] is True

    def test_a_repaired_quote_still_passes_the_exact_check(self):
        # This is the whole point: the stored text is verbatim, so the
        # database trigger and the publication re-check both still accept it.
        got, _ = self.stored("joint pain is COMMON with an aromatase inhibitor.")
        assert find_exact_quote(SECTION, got["quoted_sentence"]) == got["char_offset"]

    def test_offset_points_at_the_stored_text(self):
        got, _ = self.stored("JOINT PAIN IS COMMON WITH AN AROMATASE INHIBITOR.")
        off, q = got["char_offset"], got["quoted_sentence"]
        assert SECTION[off:off + len(q)] == q

    def test_an_exact_quote_is_not_marked_repaired(self):
        got, _ = self.stored("Joint pain is common with an aromatase inhibitor.")
        assert got["quote_repaired"] is False

    def test_curly_quotes_and_dashes_are_bridged(self):
        section = "Use the patient\u2019s own words \u2014 they matter here."
        model = "Use the patient's own words - they matter here."
        got = anchor_quote(section, model)
        assert got and got.repaired
        assert got.quoted_sentence == section, "stores the source's typography"

    def test_a_short_fragment_is_not_repaired(self):
        # Too short to re-anchor safely: a few words can land anywhere.
        assert anchor_quote(SECTION, "joint pain") is None

    def test_repair_never_invents_text(self):
        # Whatever comes back must be a literal slice of the section.
        for probe in ("joint pain is common with an aromatase inhibitor.",
                      "Some patients report double spaced text"):
            got = anchor_quote(SECTION, probe)
            assert got is not None
            assert got.quoted_sentence in SECTION

    def test_normalised_equal_is_reporting_only(self):
        assert normalised_equal("Joint  PAIN", "joint pain")
        assert not normalised_equal("joint pain", "joint ache")
