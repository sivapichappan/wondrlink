# test_connection_map_extraction.py
"""Extraction validation (SPEC §6.1, §6.2; acceptance #11, #12).

The single most important test in this file is that a quotation which is not
an EXACT substring of its section is rejected. The characteristic failure of
this pipeline is a plausible relationship carrying an invented citation, and
exact matching is the only thing that catches it every time.

Offline: no model, no database. The validators are pure by design so these
rules can be proven without either.
"""

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.concepts import (  # noqa: E402
    CONCEPT_DOMAINS,
    RELATIONSHIP_DOMAINS,
    RELATIONSHIP_TYPES,
)
from connection_map.extraction.repair import (  # noqa: E402
    anchor_quote,
    normalised_equal,
)
from connection_map.extraction.validate import (  # noqa: E402
    MIN_PASS2_EVIDENCE,
    REJECT_REASONS,
    domain_violation,
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

    def test_an_empty_candidate_list_is_normal(self):
        # A section that states no relationship is the common case and must not
        # produce a rejection. A reply that was not an ANSWER is a different
        # thing entirely and is now counted — see TestSilentModelFailures. This
        # test used to assert that `None` was also "normal", which is precisely
        # what let a broken extractor read as a quiet corpus.
        assert validate_pass1({"candidates": []}, SECTION, SLUGS, RELS) == ([], [])

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


DOMAINS = {
    "joint_pain": "symptom",
    "fatigue": "symptom",
    "aromatase_inhibitor": "treatment",
    "medication_adherence": "daily_life",
}


class TestSilentModelFailures:
    """A run that reports "0 accepted, 0 rejected" must mean the section stated
    nothing — never that the extractor was broken.

    Both of this extractor's real failures returned zero candidates silently: an
    empty list it did not mean, and the section text echoed back as
    `{"section_text": "..."}`. Neither was visible in any counter, so a genuinely
    broken run looked exactly like a quiet corpus for an entire debugging
    session. These are the counters that tell them apart.
    """

    def test_echoing_the_prompt_back_is_reported(self):
        ok, bad = validate_pass1({"section_text": SECTION}, SECTION, SLUGS, RELS)
        assert not ok
        assert [r["reason"] for r in bad] == ["no_candidate_list"]

    def test_unparsable_reply_is_reported(self):
        ok, bad = validate_pass1(parse_model_json("I cannot help with that"),
                                 SECTION, SLUGS, RELS)
        assert not ok
        assert [r["reason"] for r in bad] == ["unparsable_response"]

    def test_a_genuinely_empty_answer_is_not_a_rejection(self):
        # The legitimate case must stay silent, or the signal is worthless.
        ok, bad = validate_pass1({"candidates": []}, SECTION, SLUGS, RELS)
        assert not ok and not bad

    def test_detail_names_the_keys_without_dumping_the_section(self):
        _, bad = validate_pass1({"section_text": SECTION}, SECTION, SLUGS, RELS)
        assert "section_text" in bad[0]["detail"]
        assert SECTION not in bad[0]["detail"], "a summary, not the echoed text"

    def test_pass2_reports_it_too(self):
        ok, bad = validate_pass2({"section_text": "..."}, ["e1", "e2"], SLUGS, RELS)
        assert not ok and [r["reason"] for r in bad] == ["no_candidate_list"]

    def test_every_reason_used_is_declared(self):
        for reason in ("no_candidate_list", "unparsable_response", "wrong_domain"):
            assert reason in REJECT_REASONS


class TestRelationshipDomains:
    """`side_effect_of` runs symptom -> treatment. The prompt says so and a model
    ignored it, proposing `weight_gain --side_effect_of--> nausea`, which asserts
    that nausea is a treatment. A closed vocabulary makes the direction
    checkable, so it is checked.
    """

    def cand(self, **over):
        base = one()["candidates"][0]
        base.update(over)
        return {"candidates": [base]}

    def test_correct_direction_is_accepted(self):
        ok, bad = validate_pass1(self.cand(), SECTION, SLUGS, RELS,
                                 concept_domains=DOMAINS)
        assert len(ok) == 1 and not bad

    def test_a_symptom_on_the_treatment_end_is_rejected(self):
        ok, bad = validate_pass1(
            self.cand(src_concept_slug="joint_pain", dst_concept_slug="fatigue"),
            SECTION, SLUGS, RELS, concept_domains=DOMAINS)
        assert not ok and bad[0]["reason"] == "wrong_domain"
        assert "symptom" in bad[0]["detail"]

    def test_the_reversed_pair_is_rejected(self):
        ok, bad = validate_pass1(
            self.cand(src_concept_slug="aromatase_inhibitor",
                      dst_concept_slug="joint_pain"),
            SECTION, SLUGS, RELS, concept_domains=DOMAINS)
        assert not ok and bad[0]["reason"] == "wrong_domain"

    def test_a_treatment_cannot_co_occur(self):
        ok, bad = validate_pass1(
            self.cand(relationship="co_occurs_with",
                      dst_concept_slug="aromatase_inhibitor"),
            SECTION, SLUGS, RELS, concept_domains=DOMAINS)
        assert not ok and bad[0]["reason"] == "wrong_domain"

    def test_two_experience_concepts_may_co_occur(self):
        ok, bad = validate_pass1(
            self.cand(relationship="co_occurs_with",
                      dst_concept_slug="medication_adherence"),
            SECTION, SLUGS, RELS, concept_domains=DOMAINS)
        assert len(ok) == 1 and not bad

    def test_an_unconstrained_relationship_is_left_alone(self):
        # Only the two v1 relationships have rules; the rest are not extracted
        # yet, and a missing rule must not become a silent rejection.
        assert "indicated_by" not in RELATIONSHIP_DOMAINS
        assert domain_violation("indicated_by", "joint_pain", "fatigue", DOMAINS) is None

    def test_no_domain_map_means_no_check(self):
        ok, _ = validate_pass1(
            self.cand(src_concept_slug="aromatase_inhibitor",
                      dst_concept_slug="joint_pain"),
            SECTION, SLUGS, RELS)
        assert len(ok) == 1, "unchecked, not silently rejected"

    def test_the_rules_only_name_real_domains(self):
        for rel, rule in RELATIONSHIP_DOMAINS.items():
            assert rel in RELATIONSHIP_TYPES
            for end in ("src", "dst"):
                for domain in rule[end]:
                    assert domain in CONCEPT_DOMAINS


class TestCorroboration:
    """A second source stating a relationship the map already holds is evidence,
    not noise (owner decision D7). It becomes another evidence row on the
    existing edge instead of being discarded as a duplicate — 72 citations were
    thrown away in the first full pass-1 sweep.
    """

    TRIPLE = ("joint_pain", "aromatase_inhibitor", "side_effect_of")
    EDGE_ID = "11111111-2222-3333-4444-555555555555"

    def test_a_known_triple_becomes_a_corroboration(self):
        ok, bad = validate_pass1(one(), SECTION, SLUGS, RELS,
                                 existing_edge_ids={self.TRIPLE: self.EDGE_ID})
        assert len(ok) == 1 and not bad
        assert ok[0]["corroborates_edge_id"] == self.EDGE_ID

    def test_a_new_triple_is_still_a_new_edge(self):
        ok, _ = validate_pass1(one(), SECTION, SLUGS, RELS, existing_edge_ids={})
        assert ok[0]["corroborates_edge_id"] is None

    def test_without_edge_ids_a_duplicate_is_still_rejected(self):
        # Callers that cannot corroborate must behave exactly as before.
        ok, bad = validate_pass1(one(), SECTION, SLUGS, RELS,
                                 existing_triples=[self.TRIPLE])
        assert not ok and bad[0]["reason"] == "already_exists"

    def test_a_corroboration_gets_no_citation_discount(self):
        # THE test in this class. Being already known must not buy a candidate
        # a weaker citation check — that would be a route to an unverified
        # quotation entering the map under an edge a physician trusts.
        ok, bad = validate_pass1(one(quoted_sentence="Joint pain is caused by letrozole."),
                                 SECTION, SLUGS, RELS,
                                 existing_edge_ids={self.TRIPLE: self.EDGE_ID})
        assert not ok and bad[0]["reason"] == "quote_not_found"

    def test_a_corroboration_is_still_domain_checked(self):
        ok, bad = validate_pass1(
            {"candidates": [dict(one()["candidates"][0],
                                 src_concept_slug="aromatase_inhibitor",
                                 dst_concept_slug="joint_pain")]},
            SECTION, SLUGS, RELS, concept_domains=DOMAINS,
            existing_edge_ids={("aromatase_inhibitor", "joint_pain",
                                "side_effect_of"): self.EDGE_ID})
        assert not ok and bad[0]["reason"] == "wrong_domain"

    def test_the_same_triple_twice_in_one_reply_is_not_two_corroborations(self):
        dup = one()["candidates"][0]
        ok, bad = validate_pass1({"candidates": [dup, dict(dup)]},
                                 SECTION, SLUGS, RELS,
                                 existing_edge_ids={self.TRIPLE: self.EDGE_ID})
        assert len(ok) == 1 and bad[0]["reason"] == "duplicate_in_batch"

    def test_a_corroboration_stores_the_sources_own_words(self):
        ok, _ = validate_pass1(
            one(quoted_sentence="joint pain is COMMON with an aromatase inhibitor."),
            SECTION, SLUGS, RELS, existing_edge_ids={self.TRIPLE: self.EDGE_ID})
        assert ok[0]["quoted_sentence"] == "Joint pain is common with an aromatase inhibitor."
        assert SECTION[ok[0]["char_offset"]:][:len(ok[0]["quoted_sentence"])] \
            == ok[0]["quoted_sentence"]


class TestCorroborationMigration:
    """Static SQL guards. The DB is the real boundary here: the function refuses
    a signed edge even if a caller asks it to.
    """

    SQL = (_REPO / "supabase_migrations"
           / "2026_08_01_connection_map_corroboration.sql").read_text()

    def test_only_a_candidate_edge_may_be_corroborated(self):
        # edge_hash covers every evidence row, so adding one to an approved edge
        # would void the physician's signature.
        assert "v_status <> 'candidate'" in self.SQL
        assert "RAISE EXCEPTION" in self.SQL

    def test_the_ordinal_is_allocated_under_a_row_lock(self):
        assert "FOR UPDATE" in self.SQL
        assert "COALESCE(MAX(ordinal), -1) + 1" in self.SQL

    def test_re_running_cannot_duplicate_a_citation(self):
        assert "CREATE UNIQUE INDEX IF NOT EXISTS master_edge_evidence_one_quote_per_place" in self.SQL
        assert "DO NOTHING" in self.SQL

    def test_the_uniqueness_rule_covers_verbatim_rows_only(self):
        # An inferred (tier C) row carries its meaning in `reasoning`, not in a
        # location, so two of them on one section are not duplicates by definition.
        assert "WHERE evidence_kind = 'verbatim'" in self.SQL

    def test_the_function_is_security_invoker(self):
        # sage_review holds no INSERT on master_edge_evidence, so a reviewer
        # session cannot reach this even by calling it directly.
        assert "SECURITY INVOKER" in self.SQL
        assert "SECURITY DEFINER" not in self.SQL

    def test_search_path_is_pinned(self):
        assert "SET search_path = public, pg_temp" in self.SQL

    def test_only_the_service_role_may_execute_it(self):
        for role in ("PUBLIC", "anon", "authenticated"):
            assert f"REVOKE ALL ON FUNCTION add_evidence_to_master_edge(UUID, JSONB) FROM {role}" in self.SQL
        assert "GRANT EXECUTE ON FUNCTION add_evidence_to_master_edge(UUID, JSONB) TO service_role" in self.SQL


class TestExtractionRunnerWiring:
    """Static guards on scripts/run_connection_map_extraction.py.

    Both of these protect a fix that took a day to find and is one deleted line
    from coming back, with no test failure to announce it.
    """

    RUNNER = (_REPO / "scripts" / "run_connection_map_extraction.py").read_text()

    def test_thinking_is_disabled_on_the_extraction_call(self):
        # The extractor is a reasoning model. With thinking ON, a real 12k-char
        # section burns the whole token budget before emitting a character, and
        # json_object mode turns that into `{"candidates": []}` — a broken run
        # that looks like an empty corpus. Measured: 0 candidates with thinking
        # on, 4 with it off, same section and prompt.
        assert '"enable_thinking": False' in self.RUNNER

    def test_both_passes_supply_the_domain_map(self):
        assert self.RUNNER.count("concept_domains=domains_by_slug") == 2

    def test_a_corroboration_is_written_as_evidence_not_dropped(self):
        assert "add_evidence_to_master_edge" in self.RUNNER
        assert "existing_edge_ids=edge_id_by_triple" in self.RUNNER

    def test_only_candidate_edges_are_offered_for_corroboration(self):
        # An approved edge carries a signature; a rejected one was a clinical
        # decision. The runner does not even ask about them.
        assert '.eq("status", "candidate")' in self.RUNNER

    def test_a_new_edge_is_remembered_so_later_sections_corroborate_it(self):
        assert "edge_id_by_triple[triple] = created.data" in self.RUNNER

    def test_pass_2_batches_its_quotations(self):
        # All 131 quotations in one call returned `{"candidates": []}` in seven
        # tokens; six in one call produced a real chain. Same collapse as pass 1
        # on long sections, so the size limit is load-bearing, not tidiness.
        assert "BATCH_QUOTATIONS = 25" in self.RUNNER
        assert "rows[:BATCH_QUOTATIONS]" in self.RUNNER

    def test_pass_2_batches_are_grouped_by_shared_concept(self):
        # A chain runs THROUGH a concept, so quotations that could chain have to
        # land in the same call; arbitrary chunking would separate them.
        assert "by_concept" in self.RUNNER and "edge_concepts" in self.RUNNER

    def test_both_passes_are_limited_to_the_v1_relationships(self):
        # §4.3 enables two types in v1. The publication gate checks a version's
        # enabled_relationships, so proposing `acts_through` (authoring-only,
        # never patient-facing) would spend review on an unpublishable candidate.
        assert 'V1_RELATIONSHIPS = ("side_effect_of", "co_occurs_with")' in self.RUNNER
        assert "V1_RELATIONSHIPS)" in self.RUNNER
        assert "RELATIONSHIP_TYPES" not in self.RUNNER, \
            "pass 2 must not offer the types v1 cannot publish"

    def test_a_chained_edge_is_tier_b_and_carries_its_reasoning(self):
        assert '"tier": "B",' in self.RUNNER
        assert 'rows[0]["reasoning"] = c["reasoning"]' in self.RUNNER

    def test_the_prompt_placeholders_all_exist(self):
        # A renamed placeholder means the model receives the literal string
        # "{section_text}" and correctly reports no relationships.
        prompts = _REPO / "config" / "connection_map" / "prompts"
        for name, expected in (
            ("pass1_section.md",
             {"relationships", "concepts", "document_title", "section_ref", "section_text"}),
            ("pass2_chain.md",
             {"relationships", "concepts", "existing", "quotations"}),
        ):
            text = (prompts / name).read_text()
            found = set(re.findall(r"\{([a-z_]+)\}", text))
            assert found == expected, f"{name}: {found ^ expected}"
            for placeholder in expected:
                assert f'.replace("{{{placeholder}}}"' in self.RUNNER, \
                    f"{name} declares {{{placeholder}}} but the runner never substitutes it"
