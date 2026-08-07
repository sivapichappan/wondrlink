# test_chat_turn_recovery.py
"""A question survives the app going away, and is only ever answered once.

/api/chat runs 15 to 40 seconds and writes the answer to `messages` before it
returns. What was missing was an address to ask about afterwards: iOS suspends
the app, the socket dies, the fetch rejects, and for a brand-new thread the
client never even learned which conversation the server made. The answer sat in
Postgres and nothing asked for it.

`client_turn_id` is minted by the client before the request, so it is three
things at once: a recovery address that outlives the process, an idempotency
key, and the join point for the answer-ready push.

The push handshake is the part worth testing hard. The handler and the notify
request race, and each side reads the other's flag out of its own write, so both
can conclude a notification is due. The compare-and-swap on `notified` is what
makes that safe.

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

import index  # noqa: E402
import supabase_storage  # noqa: E402
from safety_classifier import SafetyResult  # noqa: E402


TEST_USER = {"user_id": "00000000-0000-4000-8000-000000000001"}
AUTH = {"Authorization": "Bearer test-token"}
CONV = "11111111-2222-4333-8444-555555555555"
TURN = "turn-abc-123"


@pytest.fixture()
def client():
    index.app.config["TESTING"] = True
    with index.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    with patch.object(index, "verify_token", return_value=TEST_USER):
        yield


class TestReplay:
    """A retry with the same turn id must not buy a second answer."""

    def _stored(self):
        return {
            "content": "Letrozole lowers the estrogen that feeds your cancer.",
            "conversation_id": CONV,
            "metadata": {
                "api_used": "together",
                "followups": ["How long will I take it?"],
                "sources": [{"title": "guideline.pdf"}],
                "client_turn_id": TURN,
            },
        }

    def test_an_answered_turn_is_replayed_verbatim(self, client, auth):
        with patch("supabase_storage.get_chat_turn",
                   return_value={"status": "answered", "conversation_id": CONV}), \
             patch("supabase_storage.find_answer_by_turn", return_value=self._stored()):
            resp = client.post(
                "/api/chat",
                data=json.dumps({"message": "why letrozole?", "client_turn_id": TURN}),
                headers={**AUTH, "Content-Type": "application/json"},
            )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["replayed"] is True
        assert body["answer"].startswith("Letrozole lowers")
        assert body["conversation_id"] == CONV
        assert body["followups"] == ["How long will I take it?"]

    def test_a_replay_does_not_spend_a_rate_limit_token(self, client, auth):
        """Otherwise recovering an answer you already paid for can lock you out."""
        with patch("supabase_storage.get_chat_turn",
                   return_value={"status": "answered", "conversation_id": CONV}), \
             patch("supabase_storage.find_answer_by_turn", return_value=self._stored()), \
             patch("rate_limit.check_rate_limit") as limiter:
            client.post(
                "/api/chat",
                data=json.dumps({"message": "why letrozole?", "client_turn_id": TURN}),
                headers={**AUTH, "Content-Type": "application/json"},
            )
        limiter.assert_not_called()

    def test_a_pending_turn_is_not_replayed(self):
        with patch("supabase_storage.get_chat_turn", return_value={"status": "pending"}):
            assert index._replay_answered_turn(TURN, TEST_USER["user_id"]) is None

    def test_an_answered_turn_with_no_stored_message_answers_fresh(self):
        # Persisting is best-effort; if it failed there is nothing to replay and
        # asking again is the correct fallback, not an error.
        with patch("supabase_storage.get_chat_turn", return_value={"status": "answered"}), \
             patch("supabase_storage.find_answer_by_turn", return_value=None):
            assert index._replay_answered_turn(TURN, TEST_USER["user_id"]) is None

    def test_a_storage_failure_answers_fresh_rather_than_erroring(self):
        with patch("supabase_storage.get_chat_turn", side_effect=RuntimeError("no table")):
            assert index._replay_answered_turn(TURN, TEST_USER["user_id"]) is None

    def test_a_crisis_reply_replays_with_its_card_intact(self):
        stored = {
            "content": "Call 911 now.",
            "conversation_id": CONV,
            "metadata": {
                "api_used": "safety-classifier",
                "is_crisis": True,
                "safety": {"tier": "T1"},
                "crisis_resources": {"message": "..."},
                "crisis_category": "medical_emergency",
            },
        }
        with patch("supabase_storage.get_chat_turn", return_value={"status": "answered"}), \
             patch("supabase_storage.find_answer_by_turn", return_value=stored):
            out = index._replay_answered_turn(TURN, TEST_USER["user_id"])
        assert out["is_crisis"] is True
        assert out["safety"]["tier"] == "T1"
        assert out["crisis_resources"]


class TestTheNotifyRace:
    """Exactly one notification, whichever side gets there first."""

    def test_the_handler_notifies_when_a_request_is_already_in(self):
        with patch("supabase_storage.mark_turn_answered",
                   return_value={"notify_requested": True}), \
             patch("supabase_storage.claim_turn_notification", return_value=True), \
             patch("notifications.notify") as sent:
            index._finish_turn(TURN, TEST_USER["user_id"], CONV)
        assert sent.call_count == 1
        assert sent.call_args.args[1] == "answer_ready"

    def test_the_handler_stays_quiet_when_nobody_asked(self):
        with patch("supabase_storage.mark_turn_answered",
                   return_value={"notify_requested": False}), \
             patch("notifications.notify") as sent:
            index._finish_turn(TURN, TEST_USER["user_id"], CONV)
        sent.assert_not_called()

    def test_the_handler_yields_when_the_endpoint_already_claimed(self):
        """Both sides can see the other's flag. The CAS decides."""
        with patch("supabase_storage.mark_turn_answered",
                   return_value={"notify_requested": True}), \
             patch("supabase_storage.claim_turn_notification", return_value=False), \
             patch("notifications.notify") as sent:
            index._finish_turn(TURN, TEST_USER["user_id"], CONV)
        sent.assert_not_called()

    def test_the_endpoint_notifies_when_the_answer_already_landed(self, client, auth):
        """The request arrives a moment after the handler stopped looking."""
        with patch("supabase_storage.request_turn_notify",
                   return_value={"status": "answered", "conversation_id": CONV}), \
             patch("supabase_storage.claim_turn_notification", return_value=True), \
             patch("notifications.notify") as sent:
            body = client.post(
                "/api/chat/notify_when_ready",
                data=json.dumps({"client_turn_id": TURN}),
                headers={**AUTH, "Content-Type": "application/json"},
            ).get_json()
        assert body["notified"] is True
        assert sent.call_count == 1

    def test_the_endpoint_waits_when_the_answer_is_still_coming(self, client, auth):
        with patch("supabase_storage.request_turn_notify",
                   return_value={"status": "pending"}), \
             patch("notifications.notify") as sent:
            body = client.post(
                "/api/chat/notify_when_ready",
                data=json.dumps({"client_turn_id": TURN}),
                headers={**AUTH, "Content-Type": "application/json"},
            ).get_json()
        assert body["notified"] is False
        sent.assert_not_called()

    def test_a_notification_carries_no_phi(self):
        """It renders on a lock screen. It may say an answer exists, nothing more."""
        from notifications import _COPY, KIND_ANSWER_READY
        copy = _COPY[KIND_ANSWER_READY]
        blob = f"{copy['title']} {copy['body']}".lower()
        for leak in ("cancer", "letrozole", "diagnos", "stage", "tumor", "chemo"):
            assert leak not in blob
        assert "—" not in blob and "–" not in blob


class TestTurnStatusEndpoint:
    def test_it_reports_answered_and_hands_back_the_conversation(self, client, auth):
        # The conversation id is the whole point for a brand-new thread: the
        # response that carried it died with the socket.
        with patch("supabase_storage.get_chat_turn",
                   return_value={"status": "answered", "conversation_id": CONV}):
            body = client.get(f"/api/chat/turn/{TURN}", headers=AUTH).get_json()
        assert body == {"status": "answered", "conversation_id": CONV}

    def test_an_unknown_turn_is_a_404(self, client, auth):
        with patch("supabase_storage.get_chat_turn", return_value=None):
            resp = client.get(f"/api/chat/turn/{TURN}", headers=AUTH)
        assert resp.status_code == 404


class TestItSurvivesAMissingTable:
    """Vercel deploys land minutes before a migration does. A chat route that
    500s because a recovery table has not been created yet would be a worse bug
    than the one this fixes."""

    @pytest.mark.parametrize("fn,args", [
        ("start_chat_turn", (TURN, TEST_USER["user_id"], CONV)),
        ("get_chat_turn", (TURN, TEST_USER["user_id"])),
        ("mark_turn_answered", (TURN, TEST_USER["user_id"], CONV)),
        ("request_turn_notify", (TURN, TEST_USER["user_id"])),
        ("claim_turn_notification", (TURN,)),
        ("find_answer_by_turn", (TURN, TEST_USER["user_id"])),
    ])
    def test_every_helper_swallows_a_missing_table(self, fn, args):
        with patch("supabase_storage.get_admin_client",
                   side_effect=RuntimeError('relation "chat_turn" does not exist')):
            getattr(supabase_storage, fn)(*args)  # must not raise

    def test_right_to_delete_covers_the_new_table(self):
        """MHMDA/GDPR parity: every user-data table joins the delete list."""
        source = (_REPO / "lib" / "supabase_storage.py").read_text()
        body = source.split("def delete_all_user_data")[1]
        assert "'chat_turn'" in body


class TestTheTurnIsRecorded:
    def test_a_normal_answer_stamps_the_turn_id_into_its_metadata(self):
        """Without the stamp the answer cannot be found again to replay."""
        captured = {}

        def _append(conversation_id, user_id, question, answer, metadata=None):
            captured.update(metadata or {})
            return {"ok": True, "title": None}

        with patch.object(index, "append_qa_to_conversation", side_effect=_append), \
             patch.object(index, "_finish_turn"):
            index._persist_turn(TEST_USER["user_id"], CONV, "q", "a",
                                {"api_used": "together"}, TURN)
        assert captured["client_turn_id"] == TURN

    def test_the_safety_escalation_also_closes_its_turn(self, client, auth):
        """A crisis is the reply most likely to be waited on from a lock screen."""
        finished = []
        with patch("rate_limit.check_rate_limit", return_value=(True, 99)), \
             patch.object(index, "get_consent_status", return_value={"chat_disabled": False}), \
             patch.object(index, "load_all_chunks", return_value=[]), \
             patch.object(index, "get_conversation_history_by_id", return_value=[]), \
             patch.object(index, "load_profile", return_value={}), \
             patch.object(index, "hybrid_search", return_value=[]), \
             patch.object(index, "conversation_belongs_to_user", return_value=True), \
             patch.object(index, "create_conversation", return_value=CONV), \
             patch.object(index, "append_qa_to_conversation",
                          return_value={"ok": True, "title": "t"}), \
             patch("supabase_storage.start_chat_turn"), \
             patch("supabase_storage.get_chat_turn", return_value=None), \
             patch("supabase_storage.get_account_basics", return_value={"perspective": "self"}), \
             patch("supabase_storage.log_safety_classification", return_value=True), \
             patch("llm_utils.is_greeting", return_value=False), \
             patch.object(index, "_finish_turn",
                          side_effect=lambda t, u, c: finished.append(t)), \
             patch("safety_classifier.classify_message",
                   return_value=SafetyResult(
                       tier="T1", category="cardiac", confidence=0.9,
                       rationale="r", rule_matched=True, source="llm",
                       model="m", latency_ms=1)):
            client.post(
                "/api/chat",
                data=json.dumps({"message": "my chest hurts badly",
                                 "conversation_id": "new",
                                 "client_turn_id": TURN}),
                headers={**AUTH, "Content-Type": "application/json"},
            )
        assert finished == [TURN]
