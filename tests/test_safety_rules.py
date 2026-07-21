# test_safety_rules.py
"""
Regression fence for the safety-rules migration.

The legacy lib/confidence.py _CRISIS_PATTERNS list was absorbed into
config/safety/sage-safety-rules-local-extensions.json (tiered). These tests
prove the migration lost nothing: every legacy phrase still fires, self-harm
phrases stay MH, and no legacy emergency phrase dropped below T2. Plus the
supervisor's v0.9 triggers fire and benign phrasing does not.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from safety_rules import (  # noqa: E402
    TIER_RANK,
    deterministic_match,
    emergency_number,
    load_safety_rules,
    rules_version,
    tier_max,
)
from confidence import detect_crisis_pattern  # noqa: E402


# (phrase, legacy category) — the exact list that used to live in
# lib/confidence.py _CRISIS_PATTERNS (minus the co-modifier special case,
# tested separately).
LEGACY_PATTERNS = [
    ("suicide", "self_harm"),
    ("kill myself", "self_harm"),
    ("end my life", "self_harm"),
    ("end it all", "self_harm"),
    ("hurt myself", "self_harm"),
    ("cut myself", "self_harm"),
    ("overdose", "self_harm"),
    ("took too many", "self_harm"),
    ("no reason to live", "self_harm"),
    ("better off dead", "self_harm"),
    ("want to die", "self_harm"),
    ("don't want to keep living", "self_harm"),
    ("don't want to live", "self_harm"),
    ("chest pain", "medical_emergency"),
    ("can't breathe", "medical_emergency"),
    ("cant breathe", "medical_emergency"),
    ("trouble breathing", "medical_emergency"),
    ("severe shortness of breath", "medical_emergency"),
    ("severe bleeding", "medical_emergency"),
    ("vomiting blood", "medical_emergency"),
    ("coughing up blood", "medical_emergency"),
    ("coughed up blood", "medical_emergency"),
    ("cough up blood", "medical_emergency"),
    ("coughed up bright", "medical_emergency"),
    ("coughing up bright", "medical_emergency"),
    ("spit up blood", "medical_emergency"),
    ("spitting up blood", "medical_emergency"),
    ("can't stop bleeding", "medical_emergency"),
    ("cant stop bleeding", "medical_emergency"),
    ("slurred speech", "medical_emergency"),
    ("speech is slurred", "medical_emergency"),
    ("speech is slurring", "medical_emergency"),
    ("slurring my speech", "medical_emergency"),
    ("numb on one side", "medical_emergency"),
    ("face drooping", "medical_emergency"),
    ("legs feel weak", "medical_emergency"),
    ("legs feel numb", "medical_emergency"),
    ("legs are weak", "medical_emergency"),
    ("legs getting weak", "medical_emergency"),
    ("legs are numb", "medical_emergency"),
    ("legs are getting weak", "medical_emergency"),
    ("legs are getting numb", "medical_emergency"),
    ("severe headache", "medical_emergency"),
    ("worst headache", "medical_emergency"),
    ("sudden headache", "medical_emergency"),
    ("headache with confusion", "medical_emergency"),
    ("seizure", "medical_emergency"),
    ("can't keep anything down", "urgent_oncology"),
    ("cant keep anything down", "urgent_oncology"),
    ("haven't been able to keep", "urgent_oncology"),
    ("havent been able to keep", "urgent_oncology"),
    ("uncontrolled vomiting", "urgent_oncology"),
    ("severe vomiting", "urgent_oncology"),
    ("keep vomiting", "urgent_oncology"),
    ("vomiting everything", "urgent_oncology"),
    ("belly feels stretched", "urgent_oncology"),
    ("uncontrolled diarrhea", "urgent_oncology"),
    ("severe diarrhea", "urgent_oncology"),
    ("can't urinate", "urgent_oncology"),
    ("cant urinate", "urgent_oncology"),
    ("urinary retention", "urgent_oncology"),
    ("shortness of breath", "urgent_oncology"),
    ("short of breath", "urgent_oncology"),
    ("getting very short of breath", "urgent_oncology"),
    ("dry cough", "urgent_oncology"),
    ("new cough", "urgent_oncology"),
    ("trouble catching my breath", "urgent_oncology"),
    ("fever of 100", "urgent_oncology"),
    ("fever of 101", "urgent_oncology"),
    ("fever of 102", "urgent_oncology"),
    ("fever of 103", "urgent_oncology"),
    ("high fever", "urgent_oncology"),
]


class TestLegacyMigrationFence:
    def test_every_legacy_phrase_still_fires(self):
        for phrase, _cat in LEGACY_PATTERNS:
            hit = deterministic_match(f"I am experiencing {phrase} today")
            assert hit is not None, f"legacy phrase no longer fires: {phrase!r}"

    def test_self_harm_phrases_stay_mh(self):
        for phrase, cat in LEGACY_PATTERNS:
            if cat != "self_harm":
                continue
            hit = deterministic_match(phrase)
            assert hit is not None and hit["tier"] == "MH", (
                f"self-harm phrase {phrase!r} -> {hit}"
            )

    def test_no_legacy_emergency_drops_below_t2(self):
        for phrase, cat in LEGACY_PATTERNS:
            if cat != "medical_emergency":
                continue
            hit = deterministic_match(phrase)
            assert hit is not None, phrase
            assert TIER_RANK[hit["tier"]] >= TIER_RANK["T2"], (
                f"legacy emergency phrase {phrase!r} landed at {hit['tier']}"
            )

    def test_legacy_urgent_phrases_reach_at_least_t3(self):
        for phrase, cat in LEGACY_PATTERNS:
            if cat != "urgent_oncology":
                continue
            hit = deterministic_match(phrase)
            assert hit is not None, phrase
            assert TIER_RANK[hit["tier"]] >= TIER_RANK["T3"], (
                f"legacy urgent phrase {phrase!r} landed at {hit['tier']}"
            )


class TestCoModifiers:
    def test_whats_the_point_with_despair_fires_mh(self):
        hit = deterministic_match("what's the point of trying to keep living")
        assert hit is not None and hit["tier"] == "MH"

    def test_whats_the_point_alone_does_not_fire(self):
        assert deterministic_match("what's the point of this lab test?") is None


class TestSupervisorRules:
    def test_v09_triggers_fire_at_their_tier(self):
        rules = load_safety_rules()
        assert rules["version"] == "0.9"
        # Spot-check one rule per tier from the supervisor file.
        assert deterministic_match("my face drooping started an hour ago")["tier"] == "T1"
        assert deterministic_match("I have shaking chills tonight")["tier"] == "T2"
        assert deterministic_match("constipation for 3 days now")["tier"] == "T3"
        assert deterministic_match("I keep having suicidal thoughts")["tier"] == "MH"

    def test_highest_tier_wins_on_multi_match(self):
        hit = deterministic_match("new cough and I can't breathe")
        assert hit["tier"] == "T1"

    def test_benign_messages_return_none(self):
        for msg in [
            "what are the side effects of FOLFOX?",
            "is a colonoscopy painful?",
            "my appointment is on Tuesday",
            "",
        ]:
            assert deterministic_match(msg) is None, msg


class TestHelpers:
    def test_tier_precedence(self):
        assert tier_max("T3", "T2") == "T2"
        assert tier_max("MH", "T2") == "MH"
        assert tier_max("MH", "T1") == "T1"
        assert tier_max("NONE", "T3") == "T3"
        assert tier_max("NONE", "NONE") == "NONE"

    def test_rules_version_combines_base_and_ext(self):
        assert rules_version() == "0.9+ext1"

    def test_emergency_number_default(self):
        assert emergency_number() == "911"


class TestLegacyShim:
    def test_detect_crisis_pattern_maps_tiers_to_legacy_categories(self):
        assert detect_crisis_pattern("I want to die")["category"] == "self_harm"
        assert detect_crisis_pattern("chest pain right now")["category"] == "medical_emergency"
        assert detect_crisis_pattern("severe diarrhea all day")["category"] == "urgent_oncology"
        assert detect_crisis_pattern("how do trials work?") is None
