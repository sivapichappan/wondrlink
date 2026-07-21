# test_safety_classifier.py
"""
Unit tests for lib/safety_classifier.py with a mocked Groq client:
merge matrix (LLM can raise, never lower), outage fall-open, malformed
JSON, kill switch, and the server-side caregiver patient_line rendering.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import safety_classifier  # noqa: E402
from safety_classifier import (  # noqa: E402
    SafetyResult,
    classify_message,
    classifier_enabled,
    render_patient_line,
)


def _mock_groq_response(payload: dict):
    content = json.dumps(payload)
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


class _MockClient:
    def __init__(self, payload=None, raise_exc=None, raw_content=None):
        self._payload = payload
        self._raise = raise_exc
        self._raw = raw_content
        create = self._create
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=create)
        )

    def with_options(self, **kwargs):
        return self

    def _create(self, **kwargs):
        if self._raise is not None:
            raise self._raise
        if self._raw is not None:
            message = SimpleNamespace(content=self._raw)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])
        return _mock_groq_response(self._payload)


def _classify(message, client, **ctx):
    ctx.setdefault("on_active_treatment", False)
    ctx.setdefault("perspective", "self")
    with patch("llm_utils.get_groq_client", return_value=client):
        return classify_message(message, **ctx)


LLM_T2 = {"tier": "T2", "category": "gi_severe", "confidence": 0.9,
          "rationale": "cannot keep fluids down", "rule_matched": True}
LLM_NONE = {"tier": "NONE", "category": "", "confidence": 0.8,
            "rationale": "informational question", "rule_matched": False}


class TestMergeMatrix:
    def test_floor_none_llm_t2_gives_t2(self):
        res = _classify("I have thrown up everything I drank since yesterday",
                        _MockClient(LLM_T2))
        assert res.tier == "T2" and res.source == "llm"

    def test_llm_cannot_lower_floor(self):
        # "chest pain" floor = T1; LLM says NONE — T1 must stand.
        res = _classify("chest pain right now", _MockClient(LLM_NONE))
        assert res.tier == "T1" and res.source == "merged"
        assert res.rule_matched is True

    def test_llm_raises_floor(self):
        # "new cough" floor = T3; LLM says T2 — T2 wins.
        llm = {"tier": "T2", "category": "breathing_on_treatment",
               "confidence": 0.85, "rationale": "cough with chemo context",
               "rule_matched": False}
        res = _classify("I have a new cough", _MockClient(llm))
        assert res.tier == "T2" and res.source == "merged"

    def test_mh_floor_beats_llm_t2(self):
        res = _classify("I want to die", _MockClient(LLM_T2))
        assert res.tier == "MH"

    def test_t1_outranks_mh(self):
        llm = {"tier": "T1", "category": "bleeding_severe", "confidence": 0.95,
               "rationale": "active overdose is an emergency", "rule_matched": False}
        res = _classify("I took too many of my pills an hour ago", _MockClient(llm))
        assert res.tier == "T1"

    def test_both_none(self):
        # Floor found nothing; LLM examined and confirmed NONE — provenance
        # is 'llm' (the model actively cleared it), not 'none'.
        res = _classify("what time is my appointment?", _MockClient(LLM_NONE))
        assert res.tier == "NONE" and res.source == "llm"


class TestFailureModes:
    def test_llm_exception_falls_open_to_floor(self):
        res = _classify("severe diarrhea all day",
                        _MockClient(raise_exc=TimeoutError("slow")))
        assert res.tier == "T2" and res.source == "rules-fallback"

    def test_llm_exception_with_no_floor_gives_none(self):
        res = _classify("I feel dizzy and my stools are black",
                        _MockClient(raise_exc=TimeoutError("slow")))
        assert res.tier == "NONE"

    def test_malformed_json_falls_open(self):
        res = _classify("severe diarrhea all day",
                        _MockClient(raw_content="tier is probably T2??"))
        assert res.tier == "T2" and res.source == "rules-fallback"

    def test_invalid_tier_falls_open(self):
        res = _classify("severe diarrhea all day",
                        _MockClient({"tier": "T9", "category": "x",
                                     "confidence": 1, "rationale": "",
                                     "rule_matched": True}))
        assert res.tier == "T2" and res.source == "rules-fallback"

    def test_no_client_falls_open(self):
        res = _classify("severe diarrhea all day", None)
        assert res.tier == "T2" and res.source == "rules-fallback"


class TestKillSwitch:
    def test_disabled_uses_floor_only(self, monkeypatch):
        monkeypatch.setenv("SAFETY_CLASSIFIER_ENABLED", "false")
        assert classifier_enabled() is False
        called = {"n": 0}

        def _boom():
            called["n"] += 1
            raise AssertionError("LLM must not be called when disabled")

        with patch("llm_utils.get_groq_client", side_effect=_boom):
            res = classify_message("chest pain", on_active_treatment=False,
                                   perspective="self")
        assert res.tier == "T1" and res.source == "rules"
        assert called["n"] == 0

    def test_default_is_enabled(self, monkeypatch):
        monkeypatch.delenv("SAFETY_CLASSIFIER_ENABLED", raising=False)
        assert classifier_enabled() is True


class TestPromptSafety:
    def test_system_prompt_contains_no_patient_fields(self):
        prompt = safety_classifier._build_system_prompt(True, "caregiver")
        assert "patient_name" not in prompt.lower().replace("patient_name", "patient_name")
        assert "<<RULES_JSON>>" not in prompt
        assert "<<EMERGENCY_NUMBER>>" not in prompt
        assert "on_active_treatment=true" in prompt
        assert "perspective=caregiver" in prompt

    def test_unknown_perspective_defaults_to_self(self):
        prompt = safety_classifier._build_system_prompt(False, "admin'; drop--")
        assert "perspective=self" in prompt


class TestPatientLine:
    def test_self_perspective_unchanged(self):
        line = render_patient_line("T2", "self", "Rosa")
        assert line == "This needs a doctor now. Call your care team right away."

    def test_caregiver_substitutes_name(self):
        line = render_patient_line("T2", "caregiver", "Rosa")
        assert line.startswith("Rosa needs a doctor now.")

    def test_caregiver_without_name_falls_back(self):
        line = render_patient_line("T1", "caregiver", None)
        assert line == "This is an emergency. Call 911 now."

    def test_emergency_number_config(self):
        line = render_patient_line("T1", "self", None, emergency_num="112")
        assert "112" in line and "911" not in line

    def test_mh_line_never_personalized_with_name(self):
        line = render_patient_line("MH", "caregiver", "Rosa")
        assert "Rosa" not in line
