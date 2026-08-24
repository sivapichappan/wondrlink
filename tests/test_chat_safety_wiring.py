# test_chat_safety_wiring.py
"""
Flask test-client wiring tests for the safety classifier in /api/chat:
T1/T2/MH short-circuit with the escalation card payload, and — since the
2026-08-24 gate inversion — the wall interaction: a direct prognosis ask
gets the fixed card only at tier NONE, T3 stays on the normal path so its
banner survives, everything else default-engages, and a classifier outage
falls open to engagement. The classifier itself is mocked — its own
behavior is covered by tests/test_safety_classifier.py; the wall detector
is real (lib/walls.py) and covered by tests/test_walls.py.
"""

import json
import sys
from contextlib import ExitStack
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


def _engage_mocks():
    """Make the full post-gate pipeline hermetic for default-engage tests:
    canned LLM, no verifier call, no belief writes, no lifecycle or
    conversation writes. Everything here is a module attribute of index or
    an in-handler import, so no real network is touched."""
    stack = ExitStack()
    stack.enter_context(patch.object(index, "get_llm_status",
                                     return_value={"primary_api": "test"}))
    stack.enter_context(patch.object(index, "call_llm",
                                     return_value=("Here is a real answer.", "test")))
    stack.enter_context(patch.object(index, "extract_profile_updates_from_query",
                                     return_value={}))
    stack.enter_context(patch("verify.verify_response", return_value={
        "verified": True, "recommended_action": "pass", "verifier_used": "mock"}))
    stack.enter_context(patch.dict("os.environ", {
        "FEATURE_BELIEFS_WRITE": "false", "FEATURE_EXTRACTION_SHADOW": "false"}))
    stack.enter_context(patch("supabase_storage.save_model_state",
                              return_value=True))
    stack.enter_context(patch("supabase_storage.update_lifecycle_stage_column",
                              return_value=True))
    stack.enter_context(patch("supabase_storage.append_patient_event",
                              return_value=True))
    stack.enter_context(patch.object(index, "append_qa_to_conversation",
                                     return_value={"ok": True, "title": None}))
    stack.enter_context(patch.object(index, "create_conversation",
                                     return_value="conv-1"))
    return stack


class TestWallInteraction:
    """The gate inversion (Trajectory Brief change 1): default-engage, with
    wall detection as the only remaining gate. Ordering is the contract —
    the crisis machinery always outranks a wall."""

    def test_none_direct_prognosis_gets_the_fixed_card(self, client, base_mocks):
        with patch("safety_classifier.classify_message",
                   return_value=_result("NONE", "", rule_matched=False)), \
             patch.object(index, "append_qa_to_conversation",
                          return_value={"ok": True, "title": None}), \
             patch.object(index, "create_conversation", return_value="conv-1"):
            resp = _post_chat(client, "How long do I have?")
        body = resp.get_json()
        assert body["api_used"] == "wall-prognosis"
        assert body["wall"]["type"] == "prognosis"
        assert "whole picture" in body["answer"]
        assert base_mocks["logged"] == []  # NONE is never logged

    def test_t3_direct_prognosis_stays_on_the_normal_path(self, client, base_mocks):
        """A T3 verdict must never be short-circuited by the wall card: the
        T3 banner rides on the normal path, and the canned card would
        silently drop it."""
        with _engage_mocks(), \
             patch("safety_classifier.classify_message",
                   return_value=_result("T3", "intake", rule_matched=False)):
            resp = _post_chat(client, "I have barely eaten for days. Am I dying?")
        body = resp.get_json() or {}
        assert resp.status_code == 200
        assert body.get("api_used") != "wall-prognosis"
        assert (body.get("safety") or {}).get("tier") == "T3"

    def test_everyday_life_is_engaged_not_refused(self, client, base_mocks):
        """The old off-topic refusal is gone: food, work, kids, money, and
        last night's game get real answers."""
        with _engage_mocks(), \
             patch("safety_classifier.classify_message",
                   return_value=_result("NONE", "", rule_matched=False)):
            resp = _post_chat(client, "who won the game last night?")
        body = resp.get_json() or {}
        assert resp.status_code == 200
        assert body.get("api_used") != "off-topic-filter"
        assert body.get("off_topic") is None
        assert body.get("wall") is None
        assert body.get("answer") == "Here is a real answer."


class TestFailureModes:
    def test_classifier_crash_falls_open_to_engagement(self, client, base_mocks):
        """A classifier outage degrades to default-engage (tier NONE), never
        to a refusal — the same fail-open direction the old gate had."""
        with _engage_mocks(), \
             patch("safety_classifier.classify_message",
                   side_effect=RuntimeError("boom")):
            resp = _post_chat(client, "who won the game last night?")
        body = resp.get_json() or {}
        assert resp.status_code == 200
        assert body.get("api_used") not in ("off-topic-filter", "wall-prognosis")
        assert body.get("answer") == "Here is a real answer."


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
