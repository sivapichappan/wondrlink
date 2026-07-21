# test_chat_safety_wiring.py
"""
Flask test-client wiring tests for the safety classifier in /api/chat
(Phase 4): T1/T2/MH short-circuit with the escalation card payload, T3
bypasses the tier-1 domain gate, NONE keeps today's behavior, and a
classifier outage falls open. The classifier itself is mocked — its own
behavior is covered by tests/test_safety_classifier.py.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))
sys.path.insert(0, str(_REPO / "api"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO / ".env")

import index  # noqa: E402  (api/index.py)
from safety_classifier import SafetyResult  # noqa: E402


TEST_USER = {"user_id": "00000000-0000-4000-8000-000000000001"}
AUTH = {"Authorization": "Bearer test-token"}


def _result(tier, category="test_cat", rule_matched=True, source="llm"):
    return SafetyResult(
        tier=tier, category=category, confidence=0.9,
        rationale="test rationale", rule_matched=rule_matched,
        source=source, model="test-model", latency_ms=42,
    )


@pytest.fixture()
def client():
    index.app.config["TESTING"] = True
    with index.app.test_client() as c:
        yield c


@pytest.fixture()
def base_mocks():
    """Neutralize auth, rate limit, consent, storage, and retrieval."""
    logged = []
    with patch.object(index, "verify_token", return_value=TEST_USER), \
         patch("rate_limit.check_rate_limit", return_value=(True, 99)), \
         patch.object(index, "get_consent_status",
                      return_value={"chat_disabled": False}), \
         patch.object(index, "load_all_chunks", return_value=[]), \
         patch.object(index, "get_conversation_history_by_id",
                      return_value=[]), \
         patch.object(index, "load_profile", return_value={}), \
         patch.object(index, "hybrid_search", return_value=[]), \
         patch("supabase_storage.get_account_basics",
               return_value={"perspective": "self"}), \
         patch("supabase_storage.log_safety_classification",
               side_effect=lambda *a, **k: logged.append(a) or True):
        yield {"logged": logged}


def _post_chat(client, message="hello"):
    return client.post(
        "/api/chat",
        data=json.dumps({"message": message}),
        headers={**AUTH, "Content-Type": "application/json"},
    )


class TestShortCircuit:
    def test_t1_returns_escalation_card(self, client, base_mocks):
        with patch("safety_classifier.classify_message",
                   return_value=_result("T1", "cardiac")):
            resp = _post_chat(client, "something is very wrong")
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["api_used"] == "safety-classifier"
        assert body["is_crisis"] is True
        assert body["crisis_category"] == "medical_emergency"
        assert body["urgency"]["level"] == "EMERGENCY"
        assert body["safety"]["tier"] == "T1"
        assert body["safety"]["emergency_number"] == "911"
        assert body["safety"]["offer_symptom_log"] is False
        assert "911" in body["answer"]
        assert len(base_mocks["logged"]) == 1

    def test_t2_offers_symptom_log(self, client, base_mocks):
        with patch("safety_classifier.classify_message",
                   return_value=_result("T2", "gi_severe")):
            resp = _post_chat(client, "something is wrong")
        body = resp.get_json()
        assert body["safety"]["tier"] == "T2"
        assert body["safety"]["offer_symptom_log"] is True
        assert body["urgency"]["level"] == "URGENT"
        assert body["crisis_category"] == "urgent_oncology"

    def test_mh_uses_warm_response_not_medical_card(self, client, base_mocks):
        with patch("safety_classifier.classify_message",
                   return_value=_result("MH", "self_harm")):
            resp = _post_chat(client, "struggling")
        body = resp.get_json()
        assert body["safety"]["tier"] == "MH"
        assert body["crisis_category"] == "self_harm"
        assert "988" in body["answer"]


class TestGateInteraction:
    def test_t3_bypasses_domain_gate(self, client, base_mocks):
        """T3 must NOT be off-topic-rejected even with zero oncology vocab
        and zero retrieval. The pipeline continues past the gate (deep
        pipeline failures are irrelevant here — the assertion is that the
        off-topic filter did not fire)."""
        gate_calls = []

        def _spy_gate(message, retrieved):
            gate_calls.append(message)
            return False, "no-keyword-no-retrieval"

        with patch("safety_classifier.classify_message",
                   return_value=_result("T3", "intake", rule_matched=False)), \
             patch("confidence.is_in_oncology_domain", side_effect=_spy_gate):
            resp = _post_chat(client, "barely eaten for days")
        body = resp.get_json() or {}
        assert body.get("api_used") != "off-topic-filter"
        assert body.get("off_topic") is not True
        assert gate_calls == []  # gate never consulted for non-NONE tiers

    def test_none_still_hits_domain_gate(self, client, base_mocks):
        with patch("safety_classifier.classify_message",
                   return_value=_result("NONE", "", rule_matched=False)), \
             patch("confidence.is_in_oncology_domain",
                   return_value=(False, "no-keyword-no-retrieval")):
            resp = _post_chat(client, "who won the game last night?")
        body = resp.get_json()
        assert body["api_used"] == "off-topic-filter"
        assert body["off_topic"] is True
        assert base_mocks["logged"] == []  # NONE is never logged


class TestFailureModes:
    def test_classifier_crash_falls_open_to_gate(self, client, base_mocks):
        with patch("safety_classifier.classify_message",
                   side_effect=RuntimeError("boom")), \
             patch("confidence.is_in_oncology_domain",
                   return_value=(False, "no-keyword-no-retrieval")):
            resp = _post_chat(client, "who won the game last night?")
        body = resp.get_json()
        assert body["api_used"] == "off-topic-filter"


class TestLogSymptomEndpoint:
    def test_valid_payload_appends_event(self, client):
        events = []
        with patch.object(index, "verify_token", return_value=TEST_USER), \
             patch("rate_limit.check_rate_limit", return_value=(True, 99)), \
             patch("supabase_storage.append_patient_event",
                   side_effect=lambda *a, **k: events.append((a, k)) or True):
            resp = client.post(
                "/api/safety/log_symptom",
                data=json.dumps({"tier": "T2", "category": "gi_severe",
                                 "note": "since this morning"}),
                headers={**AUTH, "Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
        assert len(events) == 1
        args, kwargs = events[0]
        assert args[1] == "symptom_report"
        assert kwargs["payload"]["tier"] == "T2"
        assert kwargs["source"] == "safety_card"

    def test_invalid_tier_rejected(self, client):
        with patch.object(index, "verify_token", return_value=TEST_USER), \
             patch("rate_limit.check_rate_limit", return_value=(True, 99)):
            resp = client.post(
                "/api/safety/log_symptom",
                data=json.dumps({"tier": "T9", "category": "x"}),
                headers={**AUTH, "Content-Type": "application/json"},
            )
        assert resp.status_code == 400

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/safety/log_symptom",
            data=json.dumps({"tier": "T2", "category": "x"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401
