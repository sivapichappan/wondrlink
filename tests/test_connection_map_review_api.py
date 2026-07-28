# test_connection_map_review_api.py
"""The review endpoints (§5.4) and the D1 edit check.

The load-bearing assertions are the acceptance-#2 ones: every /api/review/*
request resolves its data through the RESTRICTED client. Proven two ways —
get_review_client is patched and asserted called, and the privileged client is
patched to explode if anything under /api/review ever touches it.

House style: per-file sys.path bootstrap, Flask test client, per-call-site
patches, no real database.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))
sys.path.insert(0, str(_REPO / "api"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO / ".env")

from connection_map.review import copy_lint  # noqa: E402
from connection_map.review import api as review_api  # noqa: E402
import index  # noqa: E402

REVIEWER = {"id": "r-1", "role": "reviewer_attesting", "credential": "MD",
            "status": "active", "full_name": "Dr. Reviewer"}
ADMIN = {"id": "r-2", "role": "admin", "credential": "other",
         "status": "active", "full_name": "Ops Admin"}
TEST_USER = {"user_id": "00000000-0000-4000-8000-000000000009"}
AUTH = {"Authorization": "Bearer test-token", "Content-Type": "application/json"}


class FakeQuery:
    """Minimal PostgREST builder: returns canned rows per table."""

    def __init__(self, rows):
        self._rows = rows

    def __getattr__(self, name):
        def chain(*args, **kwargs):
            return self
        return chain

    def execute(self):
        result = MagicMock()
        result.data = self._rows
        return result


class FakeReviewClient:
    def __init__(self, tables=None, rpc_results=None):
        self.tables = tables or {}
        self.rpc_results = rpc_results or {}
        self.rpc_calls = []
        self.inserted = {}

    def table(self, name):
        rows = self.tables.get(name, [])
        query = FakeQuery(rows)
        original_execute = query.execute
        inserted = self.inserted

        def tracking_insert(payload):
            inserted.setdefault(name, []).append(payload)
            return query
        query.insert = tracking_insert
        query.execute = original_execute
        return query

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return FakeQuery(self.rpc_results.get(name))


def make_client(reviewer=REVIEWER, tables=None, rpc_results=None):
    fake = FakeReviewClient(tables=tables, rpc_results=rpc_results)
    fake.tables.setdefault("reviewer", [dict(reviewer)] if reviewer else [])
    return fake


@pytest.fixture()
def client():
    index.app.config["TESTING"] = True
    with index.app.test_client() as c:
        yield c


@pytest.fixture()
def authed():
    with patch.object(index, "verify_token", return_value=TEST_USER):
        yield


class TestCopyLint:
    def test_clean_copy_passes(self):
        text = "Some people taking this pill notice new joint aches. Has that been true for you?"
        assert copy_lint.lint_patient_copy(text) == []

    def test_em_dash_fails(self):
        assert copy_lint.lint_patient_copy("Joint aches — has that been true?")

    def test_causal_verbs_fail(self):
        for phrase in ("This pill causes joint pain.", "Aches due to the pill.",
                       "The pill leads to aches.", "It triggers pain."):
            assert copy_lint.lint_patient_copy(phrase), phrase

    def test_confidence_numbers_fail(self):
        assert copy_lint.lint_patient_copy("About 40% of people notice this.")
        assert copy_lint.lint_patient_copy("1 in 3 people notice this.")

    def test_long_sentences_fail(self):
        long = "word " * 30 + "end."
        assert copy_lint.lint_patient_copy(long)

    def test_empty_fails(self):
        assert copy_lint.lint_patient_copy("")
        assert copy_lint.lint_patient_copy(None)


class TestD1EditCheck:
    QUOTES = ["Joint pain is common with an aromatase inhibitor."]

    def test_reasonable_edit_produces_no_concerns(self):
        out = copy_lint.review_edit_concerns(
            "Some people taking this pill notice new joint aches. Has that been true for you?",
            quoted_sentences=self.QUOTES)
        assert out["blocking"] == []
        assert out["concerns"] == []

    def test_hard_rules_still_block_even_for_physicians(self):
        out = copy_lint.review_edit_concerns(
            "This pill causes joint pain — about 40% of the time.",
            quoted_sentences=self.QUOTES)
        assert out["blocking"], "§8 rules are the publication gate's, not advisory"

    def test_drifted_wording_is_a_concern_not_a_block(self):
        out = copy_lint.review_edit_concerns(
            "Some people notice trouble sleeping at night. Has that been true for you?",
            quoted_sentences=self.QUOTES)
        assert out["blocking"] == []
        assert any("shares no term" in c for c in out["concerns"])

    def test_statement_instead_of_question_is_a_concern(self):
        out = copy_lint.review_edit_concerns(
            "Some people notice joint aches with this pill.",
            quoted_sentences=self.QUOTES)
        assert out["blocking"] == []
        assert any("question" in c for c in out["concerns"])

    def test_never_blocks_on_clinical_grounds(self):
        # The check must have no notion of clinical right or wrong: a valid
        # framing it has never seen produces at most a concern.
        out = copy_lint.review_edit_concerns(
            "Some people notice their joints ache with this pill. Is that you?",
            quoted_sentences=self.QUOTES)
        assert out["blocking"] == []


class TestAttestationText:
    def test_v1_covers_a_and_b(self):
        for tier in ("A", "B"):
            entry = review_api.attestation_text_for_tier(tier)
            assert entry and entry["version"] == "v1"
            assert "not attesting that this relationship is true" in entry["text"]

    def test_tier_c_has_no_wording_yet(self):
        # D2: refusing is correct until the attorney-approved variant lands.
        assert review_api.attestation_text_for_tier("C") is None


class TestAuthBoundary:
    def test_no_token_is_401(self, client):
        assert client.get("/api/review/queue").status_code == 401

    def test_patient_token_is_403_uniformly(self, client, authed):
        # A patient is not a reviewer; the refusal carries no detail.
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=None)):
            resp = client.get("/api/review/queue", headers=AUTH)
        assert resp.status_code == 403
        assert resp.get_json() == {"error": "FORBIDDEN"}

    def test_revoked_reviewer_is_403_with_the_same_body(self, client, authed):
        revoked = dict(REVIEWER, status="revoked")
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=revoked)):
            resp = client.get("/api/review/queue", headers=AUTH)
        assert resp.status_code == 403
        assert resp.get_json() == {"error": "FORBIDDEN"}

    def test_boundary_error_fails_closed_as_503(self, client, authed):
        with patch.object(review_api, "get_review_client",
                          side_effect=review_api.ReviewBoundaryError("no secret")):
            resp = client.get("/api/review/queue", headers=AUTH)
        assert resp.status_code == 503


class TestAcceptance2:
    """Every /api/review/* route resolves through the restricted client."""

    def test_all_review_routes_are_registered_and_counted(self):
        rules = [r.rule for r in index.app.url_map.iter_rules()
                 if r.rule.startswith("/api/review")]
        expected = {"/api/review/queue", "/api/review/edge/<edge_id>",
                    "/api/review/edge/<edge_id>/attest",
                    "/api/review/version/<version_id>/blockers",
                    "/api/review/version/<version_id>/publish",
                    "/api/review/concept", "/api/review/meta"}
        assert set(rules) == expected

    def test_queue_uses_only_the_restricted_client(self, client, authed):
        fake = make_client()
        admin = MagicMock(side_effect=AssertionError(
            "privileged client touched from /api/review"))
        with patch.object(review_api, "get_review_client", return_value=fake), \
             patch("supabase_client.get_admin_client", admin), \
             patch("supabase_client.get_supabase_client", admin):
            resp = client.get("/api/review/queue", headers=AUTH)
        assert resp.status_code == 200
        admin.assert_not_called()

    def test_attest_routes_through_the_database_function(self, client, authed):
        fake = make_client(tables={
            "master_edge": [{"tier": "A", "status": "candidate", "rejection_reason": None}],
        }, rpc_results={"connection_map_attest": "att-1"})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.post("/api/review/edge/e-1/attest", headers=AUTH,
                               data=json.dumps({"decision": "approve"}))
        assert resp.status_code == 200
        names = [n for n, _ in fake.rpc_calls]
        assert names == ["connection_map_attest"]
        _, params = fake.rpc_calls[0]
        assert params["p_reviewer_id"] == REVIEWER["id"]
        assert params["p_text_version"] == "v1"

    def test_tier_c_attestation_is_refused_never_fallback(self, client, authed):
        fake = make_client(tables={
            "master_edge": [{"tier": "C", "status": "candidate", "rejection_reason": None}],
        })
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.post("/api/review/edge/e-1/attest", headers=AUTH,
                               data=json.dumps({"decision": "approve"}))
        assert resp.status_code == 409
        assert fake.rpc_calls == [], "no signature may be minted without approved wording"

    def test_reject_requires_a_structured_reason(self, client, authed):
        fake = make_client(tables={
            "master_edge": [{"tier": "A", "status": "candidate", "rejection_reason": None}],
        })
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.post("/api/review/edge/e-1/attest", headers=AUTH,
                               data=json.dumps({"decision": "reject"}))
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "REJECTION_REASON_REQUIRED"

    def test_publish_is_admin_only(self, client, authed):
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=REVIEWER)):
            resp = client.post("/api/review/version/v-1/publish", headers=AUTH)
        assert resp.status_code == 403

        fake = make_client(reviewer=ADMIN, rpc_results={"connection_map_publish": "v-1"})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.post("/api/review/version/v-1/publish", headers=AUTH)
        assert resp.status_code == 200
        assert [n for n, _ in fake.rpc_calls] == ["connection_map_publish"]


class TestReviewerFlagInAcknowledgement:
    """RootGate branches on is_reviewer FIRST: a reviewer routed into patient
    onboarding would end by creating a patient profile and tripping the
    exclusivity trigger. The flag must exist, and must fail to False."""

    def _call(self, client, reviewer_result):
        kwargs = ({"side_effect": reviewer_result}
                  if isinstance(reviewer_result, Exception)
                  else {"return_value": reviewer_result})
        with patch.object(index, "check_acknowledgement",
                          return_value={"acknowledged": False}), \
             patch("supabase_storage.get_cancer_slug", return_value=None), \
             patch("supabase_storage.get_account_basics",
                   return_value={"needs_basics": True}), \
             patch("supabase_storage.is_active_reviewer", **kwargs):
            return client.get("/api/check_acknowledgement", headers=AUTH)

    def test_reviewer_account_is_flagged(self, client, authed):
        resp = self._call(client, True)
        assert resp.status_code == 200
        assert resp.get_json()["is_reviewer"] is True

    def test_patient_account_is_not(self, client, authed):
        resp = self._call(client, False)
        assert resp.status_code == 200
        assert resp.get_json()["is_reviewer"] is False

    def test_lookup_failure_means_false_never_500(self, client, authed):
        # The patient flow must not depend on the review schema existing.
        resp = self._call(client, RuntimeError("reviewer table missing"))
        assert resp.status_code == 200
        assert resp.get_json()["is_reviewer"] is False


class TestEditEndpoint:
    def test_evidence_fields_are_not_editable(self, client, authed):
        with patch.object(review_api, "get_review_client", return_value=make_client()):
            resp = client.patch("/api/review/edge/e-1", headers=AUTH,
                                data=json.dumps({"quoted_sentence": "tampered"}))
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "FIELD_NOT_EDITABLE"

    def test_hard_copy_rules_block_with_422(self, client, authed):
        fake = make_client(tables={"master_edge": [{"patient_phrasing": "old"}],
                                   "master_edge_evidence": []})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.patch("/api/review/edge/e-1", headers=AUTH,
                                data=json.dumps({"patient_phrasing":
                                                 "This pill causes pain — 40% of the time."}))
        assert resp.status_code == 422
        assert resp.get_json()["error"] == "COPY_RULES"

    def test_soft_concerns_return_200_with_notes(self, client, authed):
        fake = make_client(tables={
            "master_edge": [{"id": "e-1", "patient_phrasing": "old"}],
            "master_edge_evidence": [{"quoted_sentence":
                                      "Joint pain is common with an aromatase inhibitor."}],
        })
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.patch("/api/review/edge/e-1", headers=AUTH,
                                data=json.dumps({"patient_phrasing":
                                                 "Some people notice trouble sleeping. Has that been true for you?"}))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert any("shares no term" in c for c in body.get("concerns", []))
