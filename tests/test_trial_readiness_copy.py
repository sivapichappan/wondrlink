# test_trial_readiness_copy.py
"""
The trials just-in-time ask (validate_trial_search_readiness) is rule-6 copy
(Trajectory Brief §2, mockup screen 09): it says why, names exactly what is
missing in plain words, and points at the easiest way to answer. It renders
in a raw <Text> on mobile, so it must carry no markdown; it skips
enforce_voice, so it must be dash-free by construction.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from clinical_trials import validate_trial_search_readiness  # noqa: E402


def _ctx(**kw):
    base = {"zip_code": "07030", "stage": "Stage III", "biomarkers": {"KRAS": "Mutant"},
            "treatment_line": "first", "age": 55, "gender": "female"}
    base.update(kw)
    return base


def _all_copy(r):
    for key in ("prompt_message", "just_in_time_question", "chat_prefill"):
        if r.get(key):
            yield r[key]


class TestMissingBoth:
    def test_screen_09_canonical_copy(self):
        r = validate_trial_search_readiness(_ctx(zip_code=None, stage=None))
        assert r["ready"] is False
        assert "two things" in r["prompt_message"]
        assert "whether the cancer has spread" in r["prompt_message"]
        assert "ZIP code" in r["prompt_message"]
        assert "paper from your doctor" in r["prompt_message"]
        assert r["offer_scan"] is True

    def test_empty_context_matches(self):
        r = validate_trial_search_readiness({})
        assert "two things" in r["prompt_message"]
        assert r["offer_scan"] is True


class TestMissingOne:
    def test_stage_only_offers_the_scanner(self):
        r = validate_trial_search_readiness(_ctx(stage=None))
        assert "one thing" in r["prompt_message"]
        assert "whether the cancer has spread" in r["prompt_message"]
        assert r["offer_scan"] is True
        assert "spread" in r["just_in_time_question"]

    def test_zip_only_does_not_offer_the_scanner(self):
        # A paper cannot answer a ZIP code.
        r = validate_trial_search_readiness(_ctx(zip_code=None))
        assert "one thing" in r["prompt_message"]
        assert "ZIP" in r["prompt_message"]
        assert r["offer_scan"] is False
        assert r["chat_prefill"].startswith("My ZIP code is")


class TestVoice:
    def test_no_jargon_no_markdown_no_dashes(self):
        variants = [
            validate_trial_search_readiness({}),
            validate_trial_search_readiness(_ctx(zip_code=None, stage=None)),
            validate_trial_search_readiness(_ctx(stage=None)),
            validate_trial_search_readiness(_ctx(zip_code=None)),
            validate_trial_search_readiness(_ctx(biomarkers=None, treatment_line=None)),
        ]
        for r in variants:
            for text in _all_copy(r):
                assert "—" not in text and "–" not in text, text
                assert "**" not in text, text
                # The patient never reads the internal field name.
                assert "cancer stage" not in text.lower(), text
                assert "zip_code" not in text, text

    def test_ready_profile_asks_for_nothing_critical(self):
        r = validate_trial_search_readiness(_ctx())
        assert r["ready"] is True
        assert r["missing_critical"] == []
