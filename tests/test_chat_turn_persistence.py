# test_chat_turn_persistence.py
"""Every reply /api/chat returns is also filed in the conversation.

Three paths used to return 200 and write nothing at all: the greeting
short-circuit, the T1/T2/MH safety escalation, and the off-topic refusal
(replaced by the wall card at the 2026-08-24 gate inversion). The
answer existed only in the HTTP body, so a patient who backgrounded the app
while one was in flight lost it outright, and reloading the thread afterwards
showed no sign it had ever happened. The safety escalation is the one that
matters: it is the highest-stakes reply the product makes.

The greeting path had a second defect. It returned no `conversation_id`, so a
brand-new thread whose first message was "hi" could never adopt the conversation
the server created — the client stayed on /chat/new and the greeting was
orphaned by the next real question.

Offline: Flask test client, patched storage, no database.
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
NEW_CONV = "11111111-2222-4333-8444-555555555555"


def _safety(tier, category="test_cat", source="llm"):
    return SafetyResult(
        tier=tier, category=category, confidence=0.9,
        rationale="test rationale", rule_matched=True,
        source=source, model="test-model", latency_ms=42,
    )


@pytest.fixture()
def client():
    index.app.config["TESTING"] = True
    with index.app.test_client() as c:
        yield c


@pytest.fixture()
def storage():
    """Capture what the route files, without touching a database.

    `appended` collects (conversation_id, user_id, question, answer, metadata)
    for every append_qa_to_conversation call.
    """
    appended = []

    def _append(conversation_id, user_id, question, answer, metadata=None):
        appended.append({
            "conversation_id": conversation_id, "user_id": user_id,
            "question": question, "answer": answer, "metadata": metadata or {},
        })
        return {"ok": True, "title": "A derived title"}

    with patch.object(index, "verify_token", return_value=TEST_USER), \
         patch("rate_limit.check_rate_limit", return_value=(True, 99)), \
         patch.object(index, "get_consent_status",
                      return_value={"chat_disabled": False}), \
         patch.object(index, "load_all_chunks", return_value=[]), \
         patch.object(index, "get_conversation_history_by_id", return_value=[]), \
         patch.object(index, "load_profile", return_value={}), \
         patch.object(index, "hybrid_search", return_value=[]), \
         patch.object(index, "conversation_belongs_to_user", return_value=True), \
         patch.object(index, "create_conversation", return_value=NEW_CONV), \
         patch.object(index, "append_qa_to_conversation", side_effect=_append), \
         patch("supabase_storage.get_account_basics",
               return_value={"perspective": "self"}), \
         patch("supabase_storage.log_safety_classification", return_value=True):
        yield {"appended": appended}


def _post(client, message, conversation_id="new"):
    """POST a chat turn. conversation_id='new' is the brand-new-thread case."""
    return client.post(
        "/api/chat",
        data=json.dumps({"message": message, "conversation_id": conversation_id}),
        headers={**AUTH, "Content-Type": "application/json"},
    )


class TestGreeting:
    def test_greeting_is_persisted(self, client, storage):
        with patch("llm_utils.is_greeting", return_value=True):
            resp = _post(client, "hi")
        assert resp.status_code == 200
        assert len(storage["appended"]) == 1
        row = storage["appended"][0]
        assert row["question"] == "hi"
        assert row["answer"]
        assert row["metadata"]["api_used"] == "greeting-shortcircuit"

    def test_greeting_returns_the_conversation_it_created(self, client, storage):
        """The regression: without an id the client cannot adopt the thread."""
        with patch("llm_utils.is_greeting", return_value=True):
            body = _post(client, "hello").get_json()
        assert body["conversation_id"] == NEW_CONV
        assert body["title"] == "A derived title"


class TestSafetyEscalation:
    def test_escalation_is_persisted(self, client, storage):
        with patch("llm_utils.is_greeting", return_value=False), \
             patch("safety_classifier.classify_message",
                   return_value=_safety("T1", "cardiac")):
            resp = _post(client, "my chest hurts and I cannot breathe")
        assert resp.status_code == 200
        assert len(storage["appended"]) == 1, "a crisis reply must be filed"

    def test_escalation_carries_the_metadata_the_card_branches_on(self, client, storage):
        """BotResponseCard chooses EscalationCard on metadata.safety.tier.

        Without these keys a reloaded crisis renders as an ordinary answer,
        which is a worse failure than not persisting at all.
        """
        with patch("llm_utils.is_greeting", return_value=False), \
             patch("safety_classifier.classify_message",
                   return_value=_safety("T2", "urgent_oncology")):
            _post(client, "I have a fever of 101 during chemo")
        meta = storage["appended"][0]["metadata"]
        assert meta["safety"]["tier"] == "T2"
        assert meta["is_crisis"] is True
        assert meta["crisis_resources"]
        assert meta["crisis_category"]
        assert meta["urgency"]["detected"] is True

    def test_escalation_returns_the_conversation_id(self, client, storage):
        with patch("llm_utils.is_greeting", return_value=False), \
             patch("safety_classifier.classify_message",
                   return_value=_safety("MH", "self_harm")):
            body = _post(client, "I do not want to be here any more").get_json()
        assert body["conversation_id"] == NEW_CONV


class TestWall:
    def test_prognosis_card_is_persisted(self, client, storage):
        """The wall short-circuit (gate inversion, 2026-08-24) files its
        turn like every other reply, with the wall stamped in metadata so a
        reloaded thread knows a wall fired, not an ordinary answer."""
        with patch("llm_utils.is_greeting", return_value=False), \
             patch("safety_classifier.classify_message", return_value=_safety("NONE")):
            body = _post(client, "How long do I have?").get_json()
        assert body["api_used"] == "wall-prognosis"
        assert body["wall"]["type"] == "prognosis"
        assert len(storage["appended"]) == 1
        meta = storage["appended"][0]["metadata"]
        assert meta["api_used"] == "wall-prognosis"
        assert meta["wall"]["type"] == "prognosis"
        assert body["conversation_id"] == NEW_CONV


class TestPersistNeverBreaksTheReply:
    def test_a_storage_failure_still_returns_the_crisis_card(self, client, storage):
        """Filing is best-effort. Losing it must not turn a crisis into a 500."""
        with patch("llm_utils.is_greeting", return_value=False), \
             patch("safety_classifier.classify_message",
                   return_value=_safety("T1", "cardiac")), \
             patch.object(index, "append_qa_to_conversation",
                          side_effect=RuntimeError("database is gone")):
            resp = _post(client, "my chest hurts and I cannot breathe")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["is_crisis"] is True
        assert body["safety"]["tier"] == "T1"

    def test_persist_turn_returns_none_when_no_conversation_can_be_made(self):
        with patch.object(index, "create_conversation", return_value=None):
            conv_id, title = index._persist_turn(
                TEST_USER["user_id"], None, "q", "a", {},
            )
        assert conv_id is None and title is None
