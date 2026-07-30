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
        # A real PostgREST response carries an integer count when one was asked
        # for. Leaving it a MagicMock made anything that reads `.count` blow up
        # only once a handler started using it.
        result.count = len(self._rows) if isinstance(self._rows, list) else 0
        return result


class FakeReviewClient:
    def __init__(self, tables=None, rpc_results=None, rpc_errors=None,
                 table_errors=None):
        self.tables = tables or {}
        self.rpc_results = rpc_results or {}
        # A database RAISE has to be reproducible here, or the handler paths that
        # turn one into a readable 409 cannot be tested at all.
        self.rpc_errors = rpc_errors or {}
        self.table_errors = table_errors or {}
        self.rpc_calls = []
        self.inserted = {}

    def table(self, name):
        rows = self.tables.get(name, [])
        query = FakeQuery(rows)
        original_execute = query.execute
        inserted = self.inserted
        boom = self.table_errors.get(name)

        def tracking_insert(payload):
            inserted.setdefault(name, []).append(payload)
            return query
        query.insert = tracking_insert

        if boom:
            def failing_update(payload):
                raise Exception(boom)
            query.update = failing_update
        query.execute = original_execute
        return query

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        if name in self.rpc_errors:
            raise Exception(self.rpc_errors[name])
        return FakeQuery(self.rpc_results.get(name))


def make_client(reviewer=REVIEWER, tables=None, rpc_results=None,
                rpc_errors=None, table_errors=None):
    fake = FakeReviewClient(tables=tables, rpc_results=rpc_results,
                            rpc_errors=rpc_errors, table_errors=table_errors)
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
                    "/api/review/concept", "/api/review/concept/<concept_id>",
                    "/api/review/meta"}
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
                               data=json.dumps({"decision": "approve",
                                                "expected_hash": "h-1"}))
        assert resp.status_code == 200
        names = [n for n, _ in fake.rpc_calls]
        assert names == ["connection_map_attest"]
        _, params = fake.rpc_calls[0]
        # The AUTH user id, not a reviewer id: the signing function resolves
        # the reviewer itself, so the credited signer is the one the token
        # proved rather than whatever the caller passed.
        assert params["p_auth_user_id"] == TEST_USER["user_id"]
        assert "p_reviewer_id" not in params
        assert params["p_text_version"] == "v1"

    def test_status_change_is_atomic_with_the_signature(self, client, authed):
        # It used to be a separate PostgREST update made BEFORE the signing
        # call, so a failure in between left an edge marked approved with
        # nothing signed while the UI reported "nothing was signed".
        fake = make_client(tables={
            "master_edge": [{"tier": "A", "status": "candidate", "rejection_reason": None}],
        }, rpc_results={"connection_map_attest": "att-1"})
        with patch.object(review_api, "get_review_client", return_value=fake):
            client.post("/api/review/edge/e-1/attest", headers=AUTH,
                        data=json.dumps({"decision": "approve",
                                         "expected_hash": "h-1"}))
        assert "master_edge" not in fake.inserted
        # Exactly one write path: the function that signs.
        assert [n for n, _ in fake.rpc_calls] == ["connection_map_attest"]

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


class TestRoleAuthorization:
    """Being an ACTIVE reviewer is authentication, not authorization (§5.1).

    An earlier version checked only `status == 'active'` on mutating routes,
    so an observer could edit, and status/rejection_reason were PATCH-able —
    letting an edge be marked approved with no signature behind it.
    """

    OBSERVER = dict(REVIEWER, id="r-obs", role="observer", credential="other")
    CLINICAL = dict(REVIEWER, id="r-cli", role="reviewer_clinical", credential="NP")

    def test_status_is_not_patchable(self):
        # §0 rule 1 must not depend on the publication gate noticing later.
        assert "status" not in review_api.EDITABLE_EDGE_FIELDS
        assert "rejection_reason" not in review_api.EDITABLE_EDGE_FIELDS

    def test_patch_rejects_status_with_400(self, client, authed):
        with patch.object(review_api, "get_review_client", return_value=make_client()):
            resp = client.patch("/api/review/edge/e-1", headers=AUTH,
                                data=json.dumps({"status": "approved"}))
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "FIELD_NOT_EDITABLE"

    def test_observer_cannot_edit(self, client, authed):
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=self.OBSERVER)):
            resp = client.patch("/api/review/edge/e-1", headers=AUTH,
                                data=json.dumps({"patient_phrasing": "Some people notice this. True?"}))
        assert resp.status_code == 403

    def test_observer_cannot_attest(self, client, authed):
        fake = make_client(reviewer=self.OBSERVER,
                           tables={"master_edge": [{"tier": "A", "status": "candidate",
                                                    "rejection_reason": None}]})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.post("/api/review/edge/e-1/attest", headers=AUTH,
                               data=json.dumps({"decision": "approve"}))
        assert resp.status_code == 403
        assert fake.rpc_calls == [], "no signature, and no status change either"

    def test_clinical_reviewer_may_reword_but_not_sign(self, client, authed):
        # §5.11: reviewer_clinical reviews; only a physician attests.
        fake = make_client(reviewer=self.CLINICAL,
                           tables={"master_edge": [{"id": "e-1", "patient_phrasing": "old"}],
                                   "master_edge_evidence": []})
        with patch.object(review_api, "get_review_client", return_value=fake):
            ok = client.patch("/api/review/edge/e-1", headers=AUTH,
                              data=json.dumps({"patient_phrasing":
                                               "Some people notice joint aches. Has that been true for you?"}))
        assert ok.status_code == 200

        fake2 = make_client(reviewer=self.CLINICAL,
                            tables={"master_edge": [{"tier": "A", "status": "candidate",
                                                     "rejection_reason": None}]})
        with patch.object(review_api, "get_review_client", return_value=fake2):
            denied = client.post("/api/review/edge/e-1/attest", headers=AUTH,
                                 data=json.dumps({"decision": "approve"}))
        assert denied.status_code == 403

    def test_attesting_physician_cannot_publish(self, client, authed):
        # §5.1: the person cutting the release is not the person vouching.
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=REVIEWER)):
            resp = client.post("/api/review/version/v-1/publish", headers=AUTH)
        assert resp.status_code == 403

    def test_observer_cannot_add_concepts(self, client, authed):
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=self.OBSERVER)):
            resp = client.post("/api/review/concept", headers=AUTH,
                               data=json.dumps({"slug": "x", "domain": "symptom",
                                                "display_clinical": "X"}))
        assert resp.status_code == 403

    def test_role_denials_are_uniform(self, client, authed):
        # Same body as the not-a-reviewer refusal: no capability disclosure.
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=self.OBSERVER)):
            resp = client.post("/api/review/version/v-1/publish", headers=AUTH)
        assert resp.get_json() == {"error": "FORBIDDEN"}

    def test_observer_can_still_read_the_queue(self, client, authed):
        # Read-only is the point of the role, not a lockout.
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=self.OBSERVER)):
            resp = client.get("/api/review/queue", headers=AUTH)
        assert resp.status_code == 200


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


class TestPhase3ReviewFixes:
    """Regression tests for the defects the Phase 3 adversarial review found.

    The severe one — signing was impossible for the role the app runs as —
    was invisible to the probe checklist because those probes ran as postgres.
    Its regression test is the SQL assertion below plus the sage-dev probe.
    """

    CLINICAL = dict(REVIEWER, id="r-cli", role="reviewer_clinical", credential="NP")

    def test_signing_function_is_security_definer(self):
        # SECURITY INVOKER meant it inserted as sage_review, which holds no
        # INSERT on attestation: every approval failed with permission denied.
        sql = (_REPO / "supabase_migrations"
               / "2026_07_31_connection_map_phase3_fixes.sql").read_text(encoding="utf-8")
        assert "SECURITY DEFINER" in sql
        assert "SET search_path = public, pg_temp" in sql
        # Definer rights make search_path pinning mandatory, not optional.

    def test_review_role_still_cannot_write_attestations_directly(self):
        sql = (_REPO / "supabase_migrations"
               / "2026_07_31_connection_map_phase3_fixes.sql").read_text(encoding="utf-8")
        assert "GRANT INSERT ON attestation TO sage_review" not in sql

    def test_published_content_is_frozen_at_the_database(self):
        sql = (_REPO / "supabase_migrations"
               / "2026_07_31_connection_map_phase3_fixes.sql").read_text(encoding="utf-8")
        assert "master_edge_published_is_frozen" in sql
        assert "master_edge_evidence_published_is_frozen" in sql
        assert "part of a published version and cannot be changed" in sql

    def test_only_a_draft_can_be_published(self):
        sql = (_REPO / "supabase_migrations"
               / "2026_07_31_connection_map_phase3_fixes.sql").read_text(encoding="utf-8")
        assert "only a draft can be published" in sql

    def test_urgency_is_not_editable_by_a_clinical_reviewer(self, client, authed):
        # §5.4: only a reviewer_attesting may clear an urgent flag. urgency
        # also feeds the edge hash, so a downgrade before signing would be
        # covered by the signature and leave no trace.
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=self.CLINICAL)):
            resp = client.patch("/api/review/edge/e-1", headers=AUTH,
                                data=json.dumps({"urgency": "routine"}))
        assert resp.status_code == 400
        assert "urgency" in resp.get_json()["fields"]

    def test_urgency_is_editable_by_the_attesting_physician(self, client, authed):
        fake = make_client(tables={"master_edge": [{"id": "e-1"}]})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.patch("/api/review/edge/e-1", headers=AUTH,
                                data=json.dumps({"urgency": "routine"}))
        assert resp.status_code == 200

    def test_concept_wording_can_be_authored(self, client, authed):
        # Without this route nothing could set display_patient, which the
        # publication gate requires on every concept — so no version the
        # workspace produced was publishable.
        fake = make_client(tables={"concept": [{"id": "c-1"}]})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.patch("/api/review/concept/c-1", headers=AUTH,
                                data=json.dumps({"display_patient": "the hormone pill"}))
        assert resp.status_code == 200

    def test_concept_wording_obeys_the_copy_rules(self, client, authed):
        fake = make_client(tables={"concept": [{"id": "c-1"}]})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.patch("/api/review/concept/c-1", headers=AUTH,
                                data=json.dumps({"display_patient": "the pill that causes aches"}))
        assert resp.status_code == 422
        assert resp.get_json()["error"] == "COPY_RULES"

    def test_proposed_concepts_are_validated(self, client, authed):
        fake = make_client()
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.post("/api/review/concept", headers=AUTH,
                               data=json.dumps({"slug": "Not A Slug", "domain": "vibes",
                                                "display_clinical": "x"}))
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "INVALID_CONCEPT"


class TestCopyLintHardening:
    """Gaps the Phase 3 review found in the §8 checker."""

    def test_multi_word_phrases_tolerate_real_whitespace(self):
        # Copy wraps, gets double-spaced, and picks up non-breaking spaces.
        # "leads  to" asserts cause exactly as much as "leads to".
        for text in ("This pill leads  to aches. True for you?",
                     "Aches due\nto the pill. True for you?"):
            assert copy_lint.lint_patient_copy(text), text

    def test_inflections_are_caught(self):
        for text in ("This pill causing aches. True for you?",
                     "Aches resulting in trouble. True for you?",
                     "This pill triggering aches. True for you?"):
            assert copy_lint.lint_patient_copy(text), text

    def test_confidence_in_words_is_caught(self):
        # §3 forbids rendering confidence "in any form", not just in digits.
        assert copy_lint.lint_patient_copy("Nine in ten people notice this. True for you?")
        assert copy_lint.lint_patient_copy("Most patients notice this. True for you?")

    def test_clinician_register_is_now_caught(self):
        # Short, no long word, no banned phrase — the old proxy passed it.
        text = "Patients receiving endocrine therapy frequently experience arthralgia."
        assert copy_lint.reading_grade(text) > copy_lint.MAX_GRADE
        assert copy_lint.lint_patient_copy(text)

    def test_the_spec_example_still_passes(self):
        # §5.4's own wording must not be blocked by our own lint.
        text = "Some people taking this pill notice new joint aches. Has that been true for you?"
        assert copy_lint.reading_grade(text) <= copy_lint.TARGET_GRADE
        assert copy_lint.lint_patient_copy(text) == []

    def test_between_target_and_block_is_a_concern_not_a_block(self):
        # Blocking a physician's valid wording is worse than letting grade 7
        # through with a note, so that band warns instead.
        borderline = "Some people notice discomfort in their joints and shoulders. Is that true for you?"
        grade = copy_lint.reading_grade(borderline)
        out = copy_lint.review_edit_concerns(borderline)
        if copy_lint.TARGET_GRADE < grade <= copy_lint.MAX_GRADE:
            assert out["blocking"] == []
            assert any("grade" in c for c in out["concerns"])

    def test_syllable_counter_is_sane(self):
        assert copy_lint._syllables("pain") == 1
        assert copy_lint._syllables("people") == 2
        assert copy_lint._syllables("") == 0


class TestChainReasoningInTheQueue:
    """A chained (tier B) candidate rests on two quotations combined by an
    argument no source makes. The reviewer has to see that argument, and has to
    be able to tell it apart from the quotations.
    """

    EDGE = {
        "id": "edge-b", "relationship": "co_occurs_with", "tier": "B",
        "urgency": "routine", "status": "candidate",
        "candidate_origin": "literature_scan", "patient_phrasing": None,
        "expected_prevalence_low": None, "expected_prevalence_high": None,
        "src_concept_id": "c1", "dst_concept_id": "c2",
    }

    def queue(self, client, evidence):
        fake = make_client(tables={
            "master_edge": [dict(self.EDGE)],
            "concept": [{"id": "c1", "slug": "joint_pain", "display_clinical": "joint pain",
                         "display_patient": None, "domain": "symptom"},
                        {"id": "c2", "slug": "medication_adherence",
                         "display_clinical": "adherence", "display_patient": None,
                         "domain": "daily_life"}],
            "master_edge_evidence": evidence,
            "source_document": [{"id": "d1", "title": "Guideline", "publisher": "NCI",
                                 "scope": "general_survivorship", "cancer": None}],
        })
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.get("/api/review/queue", headers=AUTH)
        assert resp.status_code == 200
        return resp.get_json()["items"][0]

    def ev(self, ordinal, reasoning=None):
        return {"master_edge_id": "edge-b", "source_document_id": "d1",
                "section_ref": f"s000{ordinal}", "quoted_sentence": f"Sentence {ordinal}.",
                "char_offset": 0, "ordinal": ordinal, "reasoning": reasoning}

    def test_the_chain_argument_reaches_the_reviewer(self):
        # It rides on an evidence row in the database; the API lifts it to the
        # edge so a client does not have to know that.
        item = self.queue(self._client,
                          [self.ev(0, "Quote 1 gives the cause, quote 2 gives the consequence."),
                           self.ev(1)])
        assert item["chain_reasoning"] == \
            "Quote 1 gives the cause, quote 2 gives the consequence."
        assert len(item["evidence"]) == 2

    def test_a_single_quotation_candidate_has_none(self):
        item = self.queue(self._client, [self.ev(0)])
        assert item["chain_reasoning"] is None

    def test_blank_reasoning_is_not_surfaced_as_an_argument(self):
        item = self.queue(self._client, [self.ev(0, "   ")])
        assert item["chain_reasoning"] is None

    def test_the_argument_is_never_presented_as_a_quotation(self):
        item = self.queue(self._client,
                          [self.ev(0, "The two sentences combine."), self.ev(1)])
        quotes = [e["quoted_sentence"] for e in item["evidence"]]
        assert item["chain_reasoning"] not in quotes

    @pytest.fixture(autouse=True)
    def _bind_client(self, client, authed):
        self._client = client


class TestSignatureIsPinnedToWhatWasOnScreen:
    """§5.6 binds an attestation to the content that was on screen when it was
    signed. It was computing the hash at signing time instead, so a corroborating
    evidence row arriving between opening a card and signing it landed inside a
    signature nobody had read. The queue now hands out the hash and the signature
    carries it back.
    """

    EDGE = {"tier": "A", "status": "candidate", "rejection_reason": None}

    def test_the_queue_hands_out_the_hash(self, client, authed):
        fake = make_client(
            tables={"master_edge": [{
                "id": "e-1", "relationship": "side_effect_of", "tier": "A",
                "urgency": "routine", "status": "candidate",
                "candidate_origin": "literature_scan", "patient_phrasing": "x",
                "expected_prevalence_low": None, "expected_prevalence_high": None,
                "src_concept_id": "c1", "dst_concept_id": "c2"}],
                    "concept": [], "master_edge_evidence": []},
            rpc_results={"connection_map_edge_hashes": [
                {"edge_id": "e-1", "edge_hash": "abc123"}]})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.get("/api/review/queue", headers=AUTH)
        assert resp.status_code == 200
        assert resp.get_json()["items"][0]["edge_hash"] == "abc123"

    def test_the_hashes_come_back_in_one_call_not_one_per_edge(self, client, authed):
        # A per-edge RPC would be one network round trip per row through
        # PostgREST, on a screen that loads a whole page at once.
        fake = make_client(tables={"master_edge": [], "concept": []})
        with patch.object(review_api, "get_review_client", return_value=fake):
            client.get("/api/review/queue", headers=AUTH)
        assert [n for n, _ in fake.rpc_calls].count("connection_map_edge_hashes") <= 1

    def test_signing_without_a_pin_is_refused(self, client, authed):
        fake = make_client(tables={"master_edge": [dict(self.EDGE)]},
                           rpc_results={"connection_map_attest": "att-1"})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.post("/api/review/edge/e-1/attest", headers=AUTH,
                               data=json.dumps({"decision": "approve"}))
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "EXPECTED_HASH_REQUIRED"
        assert fake.rpc_calls == [], "nothing may be signed without saying what"

    def test_the_pin_reaches_the_database_function(self, client, authed):
        fake = make_client(tables={"master_edge": [dict(self.EDGE)]},
                           rpc_results={"connection_map_attest": "att-1"})
        with patch.object(review_api, "get_review_client", return_value=fake):
            client.post("/api/review/edge/e-1/attest", headers=AUTH,
                        data=json.dumps({"decision": "approve",
                                         "expected_hash": "abc123"}))
        _, params = fake.rpc_calls[0]
        assert params["p_expected_hash"] == "abc123"

    def test_a_stale_edge_is_a_409_not_a_500(self, client, authed):
        # The edge moved under the reviewer. That is normal and recoverable, and
        # has to read as such: as a 500 the UI said "that did not go through",
        # inviting a retry that would fail the same way forever.
        fake = make_client(
            tables={"master_edge": [dict(self.EDGE)]},
            rpc_errors={"connection_map_attest":
                        'connection_map: STALE_EDGE this connection changed'})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.post("/api/review/edge/e-1/attest", headers=AUTH,
                               data=json.dumps({"decision": "approve",
                                                "expected_hash": "old"}))
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "STALE_EDGE"

    def test_any_other_database_failure_still_surfaces(self, client, authed):
        # Only the stale case is translated. Swallowing everything would hide a
        # real fault behind a friendly message.
        fake = make_client(tables={"master_edge": [dict(self.EDGE)]},
                           rpc_errors={"connection_map_attest": "connection died"})
        with patch.object(review_api, "get_review_client", return_value=fake):
            with pytest.raises(Exception, match="connection died"):
                client.post("/api/review/edge/e-1/attest", headers=AUTH,
                            data=json.dumps({"decision": "approve",
                                             "expected_hash": "h"}))

    def test_rewording_a_signed_edge_is_a_409_not_a_silent_void(self, client, authed):
        # This handler had no status check at all: rewording an approved edge
        # changed a hash-bearing field and voided the signature in silence, and
        # the edge only failed later at the publication gate.
        fake = make_client(
            tables={"master_edge": [{"patient_phrasing": "old"}],
                    "master_edge_evidence": [
                        {"quoted_sentence": "Joint pain is common with an aromatase inhibitor."}]},
            table_errors={"master_edge":
                          'connection_map: SIGNED_EDGE this connection has been signed'})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.patch("/api/review/edge/e-1", headers=AUTH,
                                data=json.dumps({"patient_phrasing":
                                                 "Some people notice new joint aches. Is that you?"}))
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "SIGNED_EDGE"


class TestQueueProgress:
    """The reviewer needs to know how much is left. `count` was the length of
    the response and the page cap was 50, so against 81 candidates she saw 50
    and nothing on screen or in the payload disagreed with "50 is all there is".
    """

    EDGE = {"id": "e-1", "relationship": "side_effect_of", "tier": "A",
            "urgency": "routine", "status": "candidate",
            "candidate_origin": "literature_scan", "patient_phrasing": "x",
            "expected_prevalence_low": None, "expected_prevalence_high": None,
            "src_concept_id": "c1", "dst_concept_id": "c2"}

    def test_the_response_carries_a_total(self, client, authed):
        fake = make_client(tables={"master_edge": [dict(self.EDGE)],
                                   "concept": [], "master_edge_evidence": []})
        with patch.object(review_api, "get_review_client", return_value=fake):
            body = client.get("/api/review/queue", headers=AUTH).get_json()
        assert body["total"] == body["count"] == 1

    def test_the_page_can_hold_the_whole_pilot_queue(self):
        # 81 candidates today. A cap below that hides work with no signal,
        # because there is no offset parameter to page with.
        assert review_api.QUEUE_PAGE_LIMIT >= 100
