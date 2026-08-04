# test_voice_no_em_dashes.py
"""A patient never sees an em dash. Enforced in code, not asked for in a prompt.

The style rule has been in the system prompt since the beginning and was broken
constantly. That was never really the model's fault: `chat_base.md` contains 29
em dashes and each per-cancer overlay another 10 to 46, so it is being told not
to use a mark its own instructions use throughout. A model copies the register
of its instructions far more reliably than it obeys a rule stated inside them.

And the very first question of the manual walkthrough — a plain "Hello" — came
back with one, from a HARDCODED string of ours. No model was involved at all.

So the guarantee is a deterministic pass over the text on its way out, and these
tests cover both halves: the function cannot leave one behind, and every exit
that shows a patient text actually calls it.

Offline: no LLM, no database.
"""

import ast
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "lib"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO / ".env")

from llm_utils import enforce_voice, enforce_voice_deep  # noqa: E402

DASHES = "—–―"


class TestNothingSurvives:

    CASES = [
        "Hi Maria — what would you like to talk through today?",
        "It is hard — but you are not alone.",
        "The results—good news—came back today.",
        "Endocrine therapy is the backbone — tamoxifen or an aromatase inhibitor.",
        "Some people notice joint aches – it usually settles.",
        "Call your team —— this is urgent.",
        "ends with a dash —",
        "— starts with one",
        "―horizontal bar―",
        "a — b – c ― d",
        "**bold — inside markdown**",
        "line one —\nline two",
    ]

    @pytest.mark.parametrize("text", CASES, ids=range(len(CASES)))
    def test_no_dash_survives(self, text):
        out, n = enforce_voice(text)
        assert n > 0
        assert not any(d in out for d in DASHES), repr(out)

    def test_clean_text_is_returned_untouched(self):
        # The common case. Rewriting text that was already fine is how a
        # cleanup pass introduces its own bugs.
        for text in ("no dashes here", "a hyphen-joined word", "5 to 10 minutes", ""):
            out, n = enforce_voice(text)
            assert out == text and n == 0

    def test_it_reports_how_many_it_removed(self):
        # Persisted per turn, so we can see how hard the model is pushing
        # against the rule rather than guessing.
        _out, n = enforce_voice("a — b — c")
        assert n == 2


class TestTheReplacementReadsCorrectly:
    """A filter that leaves mangled English is worse than the em dash. The
    cautionary tale is next door: soften_tone rewrites "you should" with no
    clause awareness, so "you shouldn't" becomes "it might help ton't"."""

    def test_a_parenthetical_becomes_commas(self):
        assert enforce_voice("The results—good news—came back.")[0] == \
            "The results, good news, came back."

    def test_an_aside_becomes_one_comma(self):
        assert enforce_voice("It is hard — but you are not alone.")[0] == \
            "It is hard, but you are not alone."

    def test_a_number_range_becomes_to(self):
        # "cycles 2, 3" would say something different from "cycles 2 to 3".
        assert enforce_voice("Take it for cycles 2—3.")[0] == "Take it for cycles 2 to 3."
        assert enforce_voice("5–10 minutes")[0] == "5 to 10 minutes"

    def test_a_line_leading_dash_becomes_a_bullet(self):
        # A comma at the start of a line would be nonsense.
        assert enforce_voice("— first\n— second")[0] == "- first\n- second"

    def test_it_never_leaves_a_doubled_or_orphan_comma(self):
        for text in ("a —, b", "a, — b", "hard — .", "x — ; y"):
            out, _ = enforce_voice(text)
            assert ",," not in out
            assert " ," not in out
            assert ", ." not in out and ", ;" not in out

    def test_it_never_leaves_a_double_space(self):
        assert "  " not in enforce_voice("a  —  b")[0]


class TestNestedPayloads:
    """Pre-visit, visit recap, appeal and deep research each return a dict of
    sections. Cleaning them field by field means the next field someone adds is
    missed."""

    def test_it_walks_dicts_and_lists(self):
        payload = {
            "title": "Your visit — a summary",
            "sections": [
                {"heading": "What was said", "body": "The scan was clear — good news."},
                {"heading": "Next", "body": ["Call — soon", "Rest"]},
            ],
            "count": 3,
            "ok": True,
            "nothing": None,
        }
        out = enforce_voice_deep(payload)
        blob = str(out)
        assert not any(d in blob for d in DASHES)
        # Shape and non-string values are untouched.
        assert out["count"] == 3 and out["ok"] is True and out["nothing"] is None
        assert len(out["sections"]) == 2
        assert out["sections"][1]["body"][1] == "Rest"

    def test_keys_are_left_alone(self):
        # Keys are field names the client reads, not prose. Rewriting one
        # silently breaks the contract with the app.
        out = enforce_voice_deep({"a—b": "text — here"})
        assert "a—b" in out


class TestOurOwnCannedStringsAreClean:
    """The walkthrough's question 1 is the greeting short-circuit: no model
    runs at all. An em dash there is ours, and it shipped."""

    def test_the_greeting_has_none(self):
        from llm_utils import greeting_response
        for name in ("Maria", ""):
            assert not any(d in greeting_response(name) for d in DASHES)

    def test_the_off_topic_refusal_has_none(self):
        from confidence import render_off_topic_response
        for slug in ("breast", "colorectal", None):
            assert not any(d in render_off_topic_response(slug) for d in DASHES)

    def test_the_crisis_responses_have_none(self):
        from confidence import render_crisis_response
        for cat in ("self_harm", "medical_emergency", "urgent_oncology"):
            assert not any(d in render_crisis_response(cat) for d in DASHES)

    def test_the_hedged_fallback_has_none(self):
        from verify import HEDGED_FALLBACK_RESPONSE, SOFT_DISCLAIMER_PREFIX
        for text in (HEDGED_FALLBACK_RESPONSE, SOFT_DISCLAIMER_PREFIX):
            assert not any(d in text for d in DASHES)

    def test_the_glossary_fallback_has_none(self):
        from llm_utils import GLOSSARY_FALLBACK
        assert not any(d in GLOSSARY_FALLBACK for d in DASHES)


class TestEveryPatientFacingExitIsWired:
    """A filter nobody calls is decoration. These assert the wiring, because a
    new surface added later is exactly how this reopens."""

    API = (_REPO / "api" / "index.py").read_text()

    def test_the_chat_answer_goes_through_it(self):
        assert "final_answer, _dashes = enforce_voice(final_answer)" in self.API

    def test_it_runs_after_the_tone_softener(self):
        # soften_tone can introduce text; running before it would miss that.
        assert self.API.index("soften_tone(final_answer)") < \
            self.API.index("enforce_voice(final_answer)")

    def test_the_reviewer_sandbox_chat_goes_through_it(self):
        assert "answer, _ = enforce_voice(answer)" in self.API

    @pytest.mark.parametrize("generator", [
        "generate_previsit_questions",
        "generate_visit_recap",
        "generate_insurance_appeal",
        "generate_deep_research",
    ])
    def test_every_structured_generator_is_wrapped(self, generator):
        assert f"enforce_voice_deep({generator}(" in self.API, (
            f"{generator} output reaches a patient unfiltered")

    def test_the_glossary_is_wired(self):
        src = (_REPO / "lib" / "llm_utils.py").read_text()
        assert "enforce_voice(answer)[0]" in src

    def test_the_eval_harness_sees_what_the_patient_sees(self):
        # Otherwise the metrics score text nobody is served.
        harness = (_REPO / "scripts" / "eval" / "run_evals.py").read_text()
        assert "enforce_voice(answer)" in harness

    def test_it_is_not_applied_inside_call_llm(self):
        """The one place it must NOT go.

        The extractor, verifier and modeler all call call_llm and parse JSON
        back. Rewriting punctuation inside a JSON string would corrupt them,
        and the failure would look like a model problem.
        """
        src = (_REPO / "lib" / "llm_utils.py").read_text()
        start = src.index("def call_llm(")
        end = src.index("\ndef ", start + 10)
        assert "enforce_voice" not in src[start:end]


class TestTheAnswerDoesNotPromiseWhatTheScreenHides:
    """The model writes a lead-in before its FOLLOWUPS: block — "Here are some
    questions you might explore next:". The block is stripped and rendered as
    chips, but the lead-in survived, so the answer ended by promising a list and
    then showed nothing. Reported from a device."""

    def test_the_lead_in_goes_with_the_block(self):
        from llm_utils import extract_followups
        out, ups = extract_followups(
            "Some advice here.\n\nHere are some questions you might explore next:"
            "\n\nFOLLOWUPS:\n- What does HR mean?\n- How do I manage side effects?")
        assert out == "Some advice here."
        assert len(ups) == 2

    def test_other_phrasings_too(self):
        # The old rule matched one exact sentence; this matches the shape.
        from llm_utils import extract_followups
        for lead in ("You may want to consider these questions next:",
                     "Here are a few things to ask about next:",
                     "Some questions to explore:"):
            out, _ = extract_followups(f"Advice.\n\n{lead}\n\nFOLLOWUPS:\n- One?")
            assert out == "Advice.", f"{lead!r} left behind: {out!r}"

    def test_a_genuine_list_is_left_alone(self):
        # Over-eager stripping would eat real content.
        from llm_utils import extract_followups
        text = "Ends with a real list:\nThings to bring:\n- notes\n- a friend"
        out, ups = extract_followups(text)
        assert out == text and ups == []

    def test_an_answer_with_no_block_is_untouched(self):
        from llm_utils import extract_followups
        text = "A normal answer that mentions questions for your doctor."
        out, ups = extract_followups(text)
        assert out == text and ups == []


class TestTheChatCardShowsWhatItPromises:
    """Four things reported from a real device on one screenshot."""

    CARD = (_REPO / "mobile" / "components" / "chat" / "BotResponseCard.tsx").read_text()
    RESOURCES = (_REPO / "mobile" / "components" / "chat" / "ResourcesRow.tsx").read_text()
    MARKDOWN = (_REPO / "mobile" / "components" / "chat" / "MarkdownText.tsx").read_text()
    BUBBLE = (_REPO / "mobile" / "components" / "chat" / "MessageBubble.tsx").read_text()

    def test_followups_are_not_behind_show_details(self):
        # They were below the fold, after two other sections, while the answer
        # announced them.
        assert "{hasFollowups && <FollowupChips" in self.CARD
        assert "expanded && hasFollowups" not in self.CARD

    def test_only_one_thing_on_the_card_is_called_sources(self):
        # ResourcesRow said SOURCES and SourceCitations said "N sources", so one
        # answer showed two different counts of two different things.
        assert "WHERE TO GET HELP" in self.RESOURCES
        assert ">SOURCES<" not in self.RESOURCES

    def test_the_summary_line_distinguishes_them(self):
        assert "to get help" in self.CARD
        assert "guideline" in self.CARD

    def test_thumbs_and_copy_are_gone(self):
        assert "MessageActions" not in self.CARD

    def test_both_sides_of_the_conversation_are_selectable(self):
        # react-native-markdown-display 7.0.2 has no `selectable` prop, so the
        # text rules are overridden. Both are needed: textgroup wraps a
        # paragraph, text is each inline run.
        assert "selectableRules" in self.MARKDOWN
        assert self.MARKDOWN.count("selectable") >= 3
        assert "selectable" in self.BUBBLE
