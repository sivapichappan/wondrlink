# test_answer_structure_metric.py
"""The eval metric that decides whether an answer can be skimmed.

Owner direction: three paragraphs of prose is intimidating to someone newly
diagnosed. An answer should be a lead sentence that answers the question, then
short labelled blocks, so it can be skimmed by its labels or read straight
down.

This metric is the only thing that will tell us whether the prompt change
actually produced that, so it needs to be right BEFORE the prompt moves —
otherwise the before/after numbers measure the metric's bugs.

Offline: pure string analysis, no LLM.
"""

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts" / "eval"))

import metrics  # noqa: E402


def _result(answer: str, depth: str = "standard", rid: str = "case"):
    return {
        "id": rid,
        "answer": answer,
        "response_length": depth,
        "expect": {"structure": True},
    }


def _score(answer: str, depth: str = "standard"):
    return metrics.answer_structure([_result(answer, depth)])


def _rules(answer: str, depth: str = "standard"):
    out = _score(answer, depth)
    return set(out["by_rule"].keys())


GOOD = (
    "Letrozole lowers the estrogen that feeds your cancer.\n"
    "\n"
    "## What to expect\n"
    "Hot flashes and joint stiffness are the two most common effects.\n"
    "\n"
    "## When to call your team\n"
    "- Pain that wakes you at night\n"
    "- A new lump anywhere\n"
)


class TestItAcceptsTheShapeWeWant:
    def test_lead_plus_labelled_blocks_passes(self):
        assert _score(GOOD)["value"] == 1.0

    def test_a_short_plain_answer_with_no_sections_passes(self):
        # Forcing structure onto "what does HER2 positive mean" would be worse
        # than not having it. Zero sections is always allowed.
        assert _score("HER2 positive means the cancer has more of a protein "
                      "that makes it grow faster.", "guided")["value"] == 1.0

    def test_a_lead_ending_in_a_question_mark_passes(self):
        assert _score("Have you been told which subtype you have?")["value"] == 1.0


class TestItCatchesTheWallOfProse:
    def test_too_many_sections_for_the_depth_is_flagged(self):
        wall = "Lead.\n" + "".join(
            f"\n## Section {i}\nBody text here.\n" for i in range(6))
        assert any(r.startswith("section_count_") for r in _rules(wall, "standard"))

    def test_guided_may_not_carry_three_sections(self):
        # The short level exists for people moving slowly. Three labelled
        # blocks is not the short level.
        text = "Lead.\n\n## A\nx\n\n## B\ny\n\n## C\nz\n"
        assert any(r.startswith("section_count_") for r in _rules(text, "guided"))

    def test_a_bullet_that_runs_to_a_paragraph_is_flagged(self):
        text = "Lead.\n\n## Options\n- " + ("word " * 60) + "\n- short one\n"
        assert "bullet_too_long" in _rules(text)


class TestItCatchesTheOppositeFailure:
    """A card of headings with nothing under them is not skimmable either."""

    def test_an_empty_section_is_flagged(self):
        assert "empty_section" in _rules("Lead.\n\n## What to expect\n\n## Next\nBody.\n")

    def test_a_single_bullet_section_is_flagged(self):
        # One bullet is a sentence wearing a costume.
        assert "single_bullet_section" in _rules("Lead.\n\n## Watch for\n- Just one thing\n")

    def test_a_label_longer_than_five_words_is_flagged(self):
        text = "Lead.\n\n## What you should watch out for over the coming weeks\nBody.\n"
        assert "label_too_long" in _rules(text)


class TestItRequiresTheAnswerToLeadWithTheAnswer:
    def test_opening_with_a_heading_is_flagged(self):
        assert "no_lead_sentence" in _rules("## What to expect\nBody text.\n")

    def test_opening_with_a_bullet_is_flagged(self):
        assert "no_lead_sentence" in _rules("- first point\n- second point\n")

    def test_a_lead_that_is_a_whole_paragraph_is_flagged(self):
        assert "lead_too_long" in _rules(("Some long sentence. " * 15) + "\n")

    def test_a_truncated_lead_is_flagged(self):
        assert "lead_not_a_sentence" in _rules("Letrozole lowers the estrogen that\n")


class TestItRejectsWhatTheRendererCannotShow:
    @pytest.mark.parametrize("answer,rule", [
        ("Lead.\n\n# Big heading\nBody.\n", "h1_heading"),
        ("Lead.\n\n---\n\nMore.\n", "horizontal_rule"),
        ("Lead.\n\n| a | b |\n| - | - |\n", "table"),
    ])
    def test_forbidden_formats_are_named(self, answer, rule):
        assert rule in _rules(answer)


class TestReportingIsActionable:
    def test_it_names_the_rule_that_broke(self):
        """A bare 0.62 says something regressed and gives no way to find out
        what. For a prompt change that is the whole question."""
        out = metrics.answer_structure([
            _result(GOOD, rid="ok"),
            _result("## No lead here\nBody.\n", rid="bad"),
        ])
        assert out["value"] == 0.5
        assert out["by_rule"]["no_lead_sentence"] == 1
        assert out["detail"][0]["id"] == "bad"

    def test_cases_without_a_structure_expectation_are_ignored(self):
        # The metric runs over every suite; only the structure suite opts in.
        out = metrics.answer_structure([{"id": "x", "answer": "anything", "expect": {}}])
        assert out["total"] == 0 and out["value"] == 1.0

    def test_an_empty_answer_is_a_failure_not_a_pass(self):
        assert "empty_answer" in _rules("")
