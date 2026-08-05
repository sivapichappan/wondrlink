# test_response_depth.py
"""Sage sizes the answer to the person instead of asking them to pick.

The Settings toggle (Brief / Normal / Detailed) is gone. Almost nobody touches a
setting like that, and it asked someone diagnosed last week to calibrate a thing
they have no basis for calibrating.

THE LOAD-BEARING DESIGN POINT is not the length, it is the shape of "shorter".
Owner direction: a patient moving slowly gets a short answer that ALWAYS OFFERS
MORE, with the follow-up chips carrying the depth. The old `brief` level did the
opposite — it switched the chips off, along with the resources row and the
gentle getting-to-know-you question. Reusing it would have left the people
needing the most hand-holding as the only ones with no door to walk through. So
`guided` is a new level, and several tests below exist purely to stop anyone
collapsing it back into `brief`.

The policy is pure, so this is a table of inputs. Offline: no LLM, no database.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "lib"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO / ".env")

from response_depth import DEEP, GUIDED, STANDARD, choose_depth  # noqa: E402

NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)

NEW = {"model_state": {"lifecycle_stage": "getting_to_know_you"}}
FAR = {"model_state": {"lifecycle_stage": "trial_ready"}}

TECHNICAL = ("My path report says HR+/HER2- invasive ductal carcinoma, grade 2, "
             "node-positive. How does Oncotype DX change whether I need adjuvant "
             "chemotherapy?")


def turns(n, minutes_ago=1):
    """n prior turns, the most recent `minutes_ago` back."""
    return [{"created_at": (NOW - timedelta(minutes=minutes_ago + i)).isoformat()}
            for i in range(n)][::-1]


def depth(message, profile=None, history=None, query_type="general"):
    return choose_depth(message, profile, history, query_type, now=NOW)["depth"]


class TestTheFourSignalsEachMove:
    """Each on its own, so a later change that breaks one is attributable."""

    def test_technical_language_asks_for_more(self):
        assert depth("what now?", NEW, []) == GUIDED
        assert depth(TECHNICAL, NEW, turns(2)) == DEEP

    def test_a_long_or_multipart_question_asks_for_more(self):
        short = choose_depth("Is that bad?", {}, [], now=NOW)["score"]
        long_ = choose_depth(
            "I have been on treatment for three months now and I am trying to "
            "understand what happens when it finishes, what the follow up looks "
            "like, and how often I will be seen.", {}, [], now=NOW)["score"]
        assert long_ > short

    def test_rapid_back_and_forth_asks_for_more(self):
        fast = choose_depth("and what about that?", FAR, turns(5, 1), now=NOW)["score"]
        slow = choose_depth("and what about that?", FAR, turns(5, 600), now=NOW)["score"]
        assert fast > slow

    def test_being_further_along_asks_for_more(self):
        new = choose_depth("what should I expect?", NEW, turns(2), now=NOW)["score"]
        far = choose_depth("what should I expect?", FAR, turns(2), now=NOW)["score"]
        assert far > new


class TestTheSignalsCombineSensibly:
    """The point of scoring rather than branching: no single signal runs away
    with the decision."""

    def test_a_technical_question_survives_being_newly_diagnosed(self):
        """The case that made me retune. Someone writing "HR+/HER2- invasive
        ductal carcinoma, grade 2, node-positive" is telling you what they want
        far more clearly than their lifecycle stage is telling you otherwise."""
        assert depth(TECHNICAL, NEW, turns(2)) == DEEP

    def test_a_plain_opener_from_someone_new_is_guided(self):
        assert depth("I was just diagnosed with breast cancer and I don't know "
                     "where to start.", NEW, []) == GUIDED

    def test_an_ordinary_question_gets_an_ordinary_answer(self):
        # Seven words. Neither hand-holding nor a monograph.
        assert depth("How do I manage fatigue during treatment?", {}, turns(2)) == STANDARD

    def test_someone_far_along_asking_briefly_is_not_hand_held(self):
        assert depth("is that normal?", FAR, turns(5)) == STANDARD


class TestItDegradesInsteadOfAssuming:

    def test_an_unknown_profile_is_not_treated_as_newly_diagnosed(self):
        """Defaulting an absent lifecycle stage to getting_to_know_you would
        quietly shorten answers for everyone we happen to know nothing about,
        including every reviewer-sandbox turn."""
        assert depth("What does HR+ mean?", {}, []) == STANDARD

    def test_the_sandbox_shape_works(self):
        # Synthetic profile: no model_state, no beliefs, no history.
        sandbox_profile = {"patient": {"firstName": "Sample", "age": 54},
                           "diagnosis": {"cancerType": "breast cancer"},
                           "_synthetic": True}
        assert depth("Tell me about treatment options", sandbox_profile, []) == STANDARD

    @pytest.mark.parametrize("bad", [None, "", "   "])
    def test_an_empty_message_does_not_explode(self, bad):
        assert choose_depth(bad, {}, [], now=NOW)["depth"] in (GUIDED, STANDARD, DEEP)

    def test_garbage_inputs_fall_back_rather_than_raise(self):
        for profile in ({"model_state": "not-a-dict"}, {"beliefs": 7}):
            out = choose_depth("hello", profile, [], now=NOW)
            assert out["depth"] in (GUIDED, STANDARD, DEEP)
        assert choose_depth("hi", {}, [{"created_at": "not-a-date"}], now=NOW)["depth"]

    def test_a_trial_question_is_never_shortened(self):
        """Eligibility is unforgiving of a summary. A one-line trial question
        from a newly diagnosed patient still gets a real answer."""
        assert depth("any trials?", NEW, [], query_type="clinical_trial") != GUIDED


class TestItSaysWhy:
    """`why` rides in debug_info, which is persisted per turn. Reading an
    exported run, the question should never be "why was this one short"."""

    def test_every_decision_carries_its_reasons(self):
        out = choose_depth(TECHNICAL, NEW, turns(2), now=NOW)
        assert out["why"], "no reasons given"
        assert any("technical" in w for w in out["why"])

    def test_the_reasons_are_human_readable(self):
        out = choose_depth("what now?", NEW, [], now=NOW)
        assert "newly diagnosed" in out["why"]
        assert "short question" in out["why"]

    def test_the_score_is_returned_for_tuning(self):
        assert isinstance(choose_depth("hi", {}, [], now=NOW)["score"], float)


class TestGuidedIsNotBrief:
    """The whole design rests on this distinction, and it is one careless
    `response_length in ("brief", "guided")` away from being lost."""

    SETTINGS_SRC = (_REPO / "lib" / "llm_utils.py").read_text()
    API_SRC = (_REPO / "api" / "index.py").read_text()
    POLICY_SRC = (_REPO / "lib" / "question_policy.py").read_text()

    def _settings(self, length):
        from llm_utils import get_response_settings
        return get_response_settings(length)

    def test_guided_is_shorter_than_standard(self):
        assert self._settings("guided")["max_tokens"] < self._settings("normal")["max_tokens"]

    def test_guided_keeps_the_resources_row(self):
        assert self._settings("guided")["include_resources"] is True
        assert self._settings("brief")["include_resources"] is False

    def test_guided_keeps_the_follow_up_chips(self):
        """The chips ARE the offer of more. Without them `guided` is just a
        worse answer."""
        assert 'if response_length != "brief":' in self.SETTINGS_SRC

    def test_guided_keeps_the_gentle_question(self):
        # TWO independent gates suppress it, and both are keyed on the exact
        # string "brief" rather than on "is this short", which is the only
        # reason `guided` passes them untouched.
        assert 'signals.get("response_length") == "brief"' in self.POLICY_SRC
        assert 'response_length != "brief"' in self.SETTINGS_SRC

    def test_the_policy_gate_is_reached_with_the_computed_depth(self):
        # question_policy is fed from the route's signals dict; if that stopped
        # carrying the depth, the gate would compare against None forever.
        assert '"response_length": response_length' in self.API_SRC

    def test_guided_keeps_the_resources_row_in_the_route(self):
        assert 'if response_length != "brief":' in self.API_SRC

    def test_deep_matches_detailed(self):
        assert self._settings("deep")["max_tokens"] == self._settings("detailed")["max_tokens"]

    def test_standard_matches_normal(self):
        assert self._settings("standard")["max_tokens"] == self._settings("normal")["max_tokens"]

    def test_the_non_chat_callers_are_untouched(self):
        """Glossary passes brief; pre-visit, visit recap, appeal and deep
        research pass detailed. Four of those parse JSON or assert a minimum
        length, so a smaller budget fails hard rather than shortening."""
        for length, expected_tokens in (("brief", 150), ("detailed", 400), ("normal", 250)):
            assert self._settings(length)["max_tokens"] == expected_tokens


class TestTheRouteNoLongerTrustsTheClient:

    API_SRC = (_REPO / "api" / "index.py").read_text()

    def test_chat_does_not_read_response_length_from_the_request(self):
        """Installed builds keep sending it. Honouring it would mean two people
        with identical needs get different answers because one of them once
        opened Settings."""
        assert 'response_length = data.get("response_length"' not in self.API_SRC

    def test_both_chat_routes_use_the_policy(self):
        assert self.API_SRC.count("choose_depth(") >= 2

    def test_the_reasoning_is_persisted_with_the_turn(self):
        assert '"depth": depth_info' in self.API_SRC

    def test_it_uses_the_unsanitized_message(self):
        """sanitize_query substitutes [REDACTED], which would distort both the
        word count and the jargon density."""
        assert "choose_depth(original_message" in self.API_SRC
