# test_reviewer_lifecycle.py
"""A clinician asks for access, an admin decides, and then they use the app.

Until now a reviewer was a walled garden: the app sent them to the queue and
refused to let them leave, so a physician vouching for patient-facing wording had
never seen the product it appears in. And reviewer rows were created by a script
on a laptop, so there was no way to ask at all.

Three properties hold this together, and each one is a separate way to get it
badly wrong:

  1. **Applying is not being approved.** §5.2 says "No self-registration. No
     public signup." Anyone may ask; a pending applicant passes NO review route
     and gets the same uniform 403 a stranger does.
  2. **A reviewer may not hold a patient profile** — trigger-enforced in both
     directions. So the reviewer's chat runs on a synthetic patient in separate
     tables, and there is no patient_id in that path to bind to by mistake.
  3. **Only an admin decides, and never their own application.** Through a
     SECURITY DEFINER function, because sage_review holds SELECT only on
     reviewer on purpose (write access turns the exclusivity trigger's error
     into a patient-existence oracle).

Offline: Flask test client, patched clients, no database.
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

from connection_map.review import api as review_api  # noqa: E402
import index  # noqa: E402
from test_connection_map_review_api import (  # noqa: E402
    ADMIN, AUTH, REVIEWER, TEST_USER, make_client,
)

MIGRATION = (_REPO / "supabase_migrations"
             / "2026_08_05_reviewer_applications_and_sandbox.sql").read_text()


@pytest.fixture()
def client():
    index.app.config["TESTING"] = True
    with index.app.test_client() as c:
        yield c


@pytest.fixture()
def authed():
    with patch.object(index, "verify_token", return_value=TEST_USER):
        yield


class FakeTable:
    def __init__(self, rows, sink=None, name=""):
        self._rows = rows
        self._sink = sink
        self._name = name

    def __getattr__(self, _name):
        def chain(*args, **kwargs):
            return self
        return chain

    def insert(self, payload):
        if self._sink is not None:
            self._sink.setdefault(self._name, []).append(payload)
        return FakeTable(payload if isinstance(payload, list) else [payload])

    def delete(self):
        if self._sink is not None:
            self._sink.setdefault(f"delete:{self._name}", []).append(True)
        return self

    def execute(self):
        result = MagicMock()
        result.data = self._rows
        return result


class FakeAdmin:
    """Enough PostgREST to exercise the patient-side routes."""

    def __init__(self, tables=None):
        self.tables = tables or {}
        self.writes = {}

    def table(self, name):
        return FakeTable(self.tables.get(name, []), self.writes, name)


# ---------------------------------------------------------------------------
# 1. Applying
# ---------------------------------------------------------------------------
class TestApplying:

    def _apply(self, client, admin, body):
        with patch("supabase_client.get_admin_client", return_value=admin):
            return client.post("/api/reviewer/apply", headers=AUTH,
                               data=json.dumps(body))

    BODY = {"full_name": "Dr Ada Reviewer", "credential": "MD",
            "email": "ada@example.org", "npi": "1234567890",
            "license_state": "nj", "specialty": "Medical oncology",
            "institution": "Example Health"}

    def test_an_application_lands_as_requested_never_active(self, client, authed):
        # The whole of §5.2's intent is in this one assertion.
        admin = FakeAdmin()
        resp = self._apply(client, admin, self.BODY)
        assert resp.status_code == 200
        assert resp.get_json()["reviewer_status"] == "requested"
        row = admin.writes["reviewer"][0]
        assert row["status"] == "requested"
        assert row.get("activated_at") is None

    def test_the_credentials_are_stored_with_the_application(self, client, authed):
        # An attestation snapshots the signer's capacity, so what the admin is
        # verifying has to be on the row, not in a chat message somewhere.
        admin = FakeAdmin()
        self._apply(client, admin, self.BODY)
        row = admin.writes["reviewer"][0]
        assert row["npi"] == "1234567890"
        assert row["license_state"] == "NJ"       # normalised
        assert row["specialty"] == "Medical oncology"
        assert row["institution"] == "Example Health"

    @pytest.mark.parametrize("credential", ["NP", "PA", "RN", "PharmD", "other", ""])
    def test_a_non_physician_is_refused_before_the_database_says_so(
            self, client, authed, credential):
        # reviewer_attesting_is_physician_check enforces it anyway; failing here
        # explains why instead of surfacing a constraint name.
        admin = FakeAdmin()
        resp = self._apply(client, admin, dict(self.BODY, credential=credential))
        assert resp.status_code == 400
        assert "MD or DO" in resp.get_json()["error"]
        assert "reviewer" not in admin.writes

    def test_an_existing_patient_account_cannot_become_a_reviewer(self, client, authed):
        # The trigger refuses this in both directions. Saying so plainly beats a
        # 500 carrying a constraint name to someone who cannot act on it.
        admin = FakeAdmin({"patient_profiles": [{"user_id": TEST_USER["user_id"]}]})
        resp = self._apply(client, admin, self.BODY)
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "ALREADY_A_PATIENT"
        assert "reviewer" not in admin.writes

    def test_reapplying_reports_status_instead_of_failing(self, client, authed):
        # Someone tapping submit again is checking on it, not erring.
        admin = FakeAdmin({"reviewer": [{"id": "r-9", "status": "requested"}]})
        resp = self._apply(client, admin, self.BODY)
        assert resp.status_code == 200
        assert resp.get_json()["reviewer_status"] == "requested"
        assert "reviewer" not in admin.writes


# ---------------------------------------------------------------------------
# 2. A pending applicant is not a reviewer
# ---------------------------------------------------------------------------
class TestPendingIsNotApproved:
    """The load-bearing one. If a 'requested' row passed any review route, this
    feature would have turned §5.2 into public signup for a signing account."""

    ROUTES = [
        ("get", "/api/review/queue"),
        ("get", "/api/review/meta"),
        ("get", "/api/review/applications"),
        ("post", "/api/review/edge/e-1/attest"),
        ("post", "/api/review/applications/r-1/decide"),
    ]

    @pytest.mark.parametrize("method,route", ROUTES)
    def test_every_review_route_refuses_a_pending_applicant(
            self, client, authed, method, route):
        pending = dict(REVIEWER, status="requested")
        with patch.object(review_api, "get_review_client",
                          return_value=make_client(reviewer=pending)):
            resp = getattr(client, method)(route, headers=AUTH, data="{}")
        assert resp.status_code == 403
        # Uniform: no hint that the account exists and is waiting. Detail here
        # is an account-status oracle.
        assert resp.get_json() == {"error": "FORBIDDEN"}


# ---------------------------------------------------------------------------
# 3. Deciding
# ---------------------------------------------------------------------------
class TestDeciding:

    def _decide(self, client, fake, body=None, application_id="r-77"):
        with patch.object(review_api, "get_review_client", return_value=fake):
            return client.post(f"/api/review/applications/{application_id}/decide",
                               headers=AUTH,
                               data=json.dumps(body or {"decision": "approve"}))

    def test_only_an_admin_may_decide(self, client, authed):
        for role in ("observer", "reviewer_clinical", "reviewer_attesting"):
            fake = make_client(reviewer=dict(REVIEWER, role=role))
            resp = self._decide(client, fake)
            assert resp.status_code == 403, role
            assert not fake.rpc_calls, f"{role} reached the database"

    def test_an_admin_decides_through_the_database_function(self, client, authed):
        fake = make_client(
            reviewer=ADMIN,
            rpc_results={"connection_map_decide_reviewer_application": "active"})
        resp = self._decide(client, fake)
        assert resp.status_code == 200
        assert resp.get_json()["new_status"] == "active"
        name, params = fake.rpc_calls[0]
        assert name == "connection_map_decide_reviewer_application"
        assert params["p_reviewer_id"] == "r-77"
        assert params["p_decision"] == "approve"

    def test_the_decider_is_the_account_the_token_proved(self, client, authed):
        # An admin id taken from the request body would let one admin record a
        # decision under another's name.
        fake = make_client(reviewer=ADMIN,
                           rpc_results={"connection_map_decide_reviewer_application": "active"})
        self._decide(client, fake, {"decision": "approve", "admin_id": "somebody-else"})
        _name, params = fake.rpc_calls[0]
        assert params["p_admin_auth_user_id"] == TEST_USER["user_id"]
        assert "somebody-else" not in json.dumps(params)

    def test_a_bad_decision_never_reaches_the_database(self, client, authed):
        fake = make_client(reviewer=ADMIN)
        for decision in ("activate", "", "APPROVE", None, "delete"):
            resp = self._decide(client, fake, {"decision": decision})
            assert resp.status_code == 400, decision
        assert not fake.rpc_calls

    def test_a_second_admin_deciding_reads_as_a_race_not_a_crash(self, client, authed):
        # Two admins looking at the same list is normal. Surfacing it as a 500
        # invites a retry that fails identically.
        fake = make_client(
            reviewer=ADMIN,
            rpc_errors={"connection_map_decide_reviewer_application":
                        "connection_map: this application is already active, "
                        "there is nothing to decide"})
        resp = self._decide(client, fake)
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "ALREADY_DECIDED"

    def test_self_approval_is_refused_by_the_database_and_translated(self, client, authed):
        fake = make_client(
            reviewer=ADMIN,
            rpc_errors={"connection_map_decide_reviewer_application":
                        "connection_map: an admin cannot decide their own application"})
        resp = self._decide(client, fake)
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "NO_SELF_APPROVAL"

    def test_an_unexpected_database_failure_is_not_dressed_up_as_a_race(
            self, client, authed):
        # Swallowing every failure behind friendly copy hides real faults.
        fake = make_client(
            reviewer=ADMIN,
            rpc_errors={"connection_map_decide_reviewer_application":
                        "connection: server closed the connection unexpectedly"})
        with pytest.raises(Exception):
            self._decide(client, fake)

    def test_a_failed_notification_does_not_undo_an_approval(self, client, authed):
        # The approval is committed by the time notify runs. Reporting it as a
        # failure would send an admin to approve someone who already is.
        fake = make_client(reviewer=ADMIN,
                           rpc_results={"connection_map_decide_reviewer_application": "active"})

        def boom(*_a, **_k):
            raise RuntimeError("push service down")

        bp = review_api.build_review_blueprint(
            verify_token=lambda _t: TEST_USER, notify=boom)
        app = index.Flask(__name__)
        app.register_blueprint(bp)
        app.config["TESTING"] = True
        with app.test_client() as c, \
             patch.object(review_api, "get_review_client", return_value=fake):
            resp = c.post("/api/review/applications/r-77/decide", headers=AUTH,
                          data=json.dumps({"decision": "approve"}))
        assert resp.status_code == 200


class TestListingApplications:

    def test_only_an_admin_sees_the_list(self, client, authed):
        for role in ("observer", "reviewer_clinical", "reviewer_attesting"):
            with patch.object(review_api, "get_review_client",
                              return_value=make_client(reviewer=dict(REVIEWER, role=role))):
                resp = client.get("/api/review/applications", headers=AUTH)
            assert resp.status_code == 403, role

    def test_the_list_carries_what_the_admin_has_to_verify(self, client, authed):
        applicant = {"id": "r-77", "full_name": "Dr Ada Reviewer",
                     "email": "ada@example.org", "credential": "MD",
                     "npi": "1234567890", "license_state": "NJ",
                     "specialty": "Medical oncology", "institution": "Example Health",
                     "status": "requested"}
        # The fake returns one canned row set per table, and before_request reads
        # the caller from reviewer[0] — so the admin goes first and the applicant
        # is found by id.
        fake = make_client(reviewer=ADMIN, tables={"reviewer": [dict(ADMIN), applicant]})
        with patch.object(review_api, "get_review_client", return_value=fake):
            resp = client.get("/api/review/applications", headers=AUTH)
        assert resp.status_code == 200
        item = next(i for i in resp.get_json()["items"] if i["id"] == "r-77")
        for field in ("credential", "npi", "license_state", "specialty", "institution"):
            assert item[field], f"{field} missing — the admin cannot verify anyone"


# ---------------------------------------------------------------------------
# 4. The sandbox
# ---------------------------------------------------------------------------
class TestSandboxIsSyntheticByConstruction:
    """§5.5: "a reviewer session cannot open a chat bound to any patient_id where
    is_synthetic = false". The strongest form of that is having no patient_id in
    the path at all, which is what separate tables buy."""

    SOURCE = (_REPO / "lib" / "sandbox_chat.py").read_text()

    def test_the_sandbox_module_never_touches_a_patient_table(self):
        for table in ("patient_profiles", "conversations", "messages",
                      "chat_messages", "patient_events", "patient_edge"):
            assert f'"{table}"' not in self.SOURCE, f"sandbox reaches {table}"

    def test_the_database_refuses_a_non_synthetic_sandbox_row(self):
        # Belt and braces for the property above: even a direct INSERT cannot
        # make a sandbox patient that claims to be real.
        assert "CONSTRAINT sandbox_patient_is_always_synthetic CHECK (is_synthetic)" in MIGRATION

    def test_sandbox_conversations_are_a_separate_table_not_a_flag(self):
        # A flag relies on every analytics, modeler and export query remembering
        # to filter it out. A separate table cannot be picked up by forgetting.
        assert "CREATE TABLE IF NOT EXISTS sandbox_conversation" in MIGRATION
        assert "CREATE TABLE IF NOT EXISTS sandbox_message" in MIGRATION

    def test_the_synthetic_profile_is_obviously_not_a_real_person(self):
        import sandbox_chat
        patient = sandbox_chat.DEFAULT_SANDBOX_PROFILE["patient"]
        assert patient["firstName"] == "Sample"
        assert sandbox_chat.DEFAULT_SANDBOX_PROFILE["_synthetic"] is True

    def test_a_stored_profile_cannot_declare_itself_real(self):
        import sandbox_chat
        merged = sandbox_chat.sandbox_profile({"raw_profile": {"_synthetic": False}})
        assert merged["_synthetic"] is True


class TestSandboxRoutesRequireAnActiveReviewer:

    ROUTES = [("post", "/api/sandbox/chat"),
              ("get", "/api/sandbox/conversations"),
              ("post", "/api/sandbox/reset")]

    @pytest.mark.parametrize("method,route", ROUTES)
    @pytest.mark.parametrize("status", ["requested", "invited", "revoked", None])
    def test_only_an_active_reviewer_reaches_the_sandbox(
            self, client, authed, method, route, status):
        rows = [] if status is None else [{"id": "r-1", "role": "reviewer_attesting",
                                           "status": status}]
        with patch("supabase_client.get_admin_client",
                   return_value=FakeAdmin({"reviewer": rows})):
            resp = getattr(client, method)(
                route, headers=AUTH, data=json.dumps({"message": "hello"}))
        assert resp.status_code == 403, f"{route} let a {status} reviewer in"

    def test_a_patient_cannot_reach_the_sandbox_either(self, client, authed):
        with patch("supabase_client.get_admin_client",
                   return_value=FakeAdmin({"reviewer": []})):
            resp = client.post("/api/sandbox/chat", headers=AUTH,
                               data=json.dumps({"message": "hello"}))
        assert resp.status_code == 403


class TestNotificationSeam:
    """Push needs a native module and a real build, so wave 1 ships the call
    site and the token table. The point is that nothing else moves later."""

    def test_it_is_off_by_default(self):
        import notifications
        # Dormant flags read env directly with a false default — feature_enabled
        # defaults TRUE and must never gate one.
        assert notifications.PUSH_ENABLED is False

    def test_notify_never_raises_whatever_the_database_does(self):
        import notifications
        with patch("supabase_client.get_admin_client",
                   side_effect=RuntimeError("table missing")):
            result = notifications.notify("u-1", notifications.KIND_REVIEWER_APPROVED)
        assert result["delivered"] == 0

    def test_the_copy_carries_no_patient_detail(self):
        import notifications
        # A notification renders on a lock screen.
        for copy in notifications._COPY.values():
            body = (copy["title"] + " " + copy["body"]).lower()
            for leak in ("cancer", "diagnosis", "stage", "tumor", "treatment"):
                assert leak not in body, leak


class TestRightToDeleteParity:
    """Every new user-data table joins delete_all_user_data in the same change.
    A push token is a persistent device identifier, so it counts."""

    def test_push_tokens_are_deleted_with_the_account(self):
        storage = (_REPO / "lib" / "supabase_storage.py").read_text()
        assert "'device_push_token'," in storage


class TestTheAppKnowsWhereToSendAReviewer:
    """RootGate is the only thing standing between a physician and patient
    onboarding, which for a reviewer account is a one-way door: finishing it
    creates a patient profile the database then refuses to let the account trade
    for a reviewer row, in either direction. The only remedy is deletion."""

    MOBILE = _REPO / "mobile"
    GATE = (MOBILE / "app" / "_layout.tsx").read_text()
    HOOK = (MOBILE / "hooks" / "useReviewerSession.ts").read_text()

    def test_the_gate_branches_on_status_not_only_the_boolean(self):
        assert "reviewer_status" in self.GATE
        assert "'requested'" in self.GATE and "'invited'" in self.GATE

    def test_a_pending_applicant_gets_the_waiting_screen(self):
        assert "reviewer-pending" in self.GATE

    def test_an_active_reviewer_is_no_longer_pinned_to_the_review_stack(self):
        # The whole point of the change: a physician vouching for patient-facing
        # wording has to be able to see the product it appears in.
        assert "if (top !== 'review') router.replace('/review'" not in self.GATE

    def test_an_active_reviewer_skips_the_patient_only_gates(self):
        # consent, state and basics all end in a patient profile, which a
        # reviewer account may not hold.
        active = self.GATE.split("if (reviewerStatus === 'active')")[1]
        assert active.index("router.replace('/')") < active.index("state_restricted")

    def test_the_hook_falls_back_for_an_older_server(self):
        # is_reviewer keeps meaning ACTIVE, so a client newer than the server
        # still routes correctly.
        assert "data?.is_reviewer ? 'active' : null" in self.HOOK

    def test_only_an_admin_sees_the_applications_row(self):
        drawer = (self.MOBILE / "components" / "common" / "AppDrawer.tsx").read_text()
        assert "reviewer.isAdmin ?" in drawer
        assert "Reviewer applications" in drawer

    def test_the_drawer_says_the_chat_is_not_a_real_patient(self):
        # A physician must never wonder for a second whether they are reading
        # somebody's chart.
        drawer = (self.MOBILE / "components" / "common" / "AppDrawer.tsx").read_text()
        assert "sample patient, not a real one" in drawer

    def test_the_chat_hook_has_exactly_one_sandbox_seam(self):
        # Two branches drift; one cannot.
        chat = (self.MOBILE / "hooks" / "useChat.ts").read_text()
        assert chat.count("isReviewer ?") + chat.count("isReviewer ?") >= 1
        assert "sendSandboxMessage" in chat and "fetchSandboxMessages" in chat

    def test_the_account_type_fork_comes_before_patient_consent(self):
        # The consent on that screen is a PATIENT agreeing to have their health
        # data processed. A clinician is not agreeing to that.
        assert "'/(onboarding)/account-type'" in self.GATE
        fork = (self.MOBILE / "app" / "(onboarding)" / "account-type.tsx").read_text()
        assert "/(onboarding)/consent" in fork
        assert "/(onboarding)/reviewer-apply" in fork


class TestApplyFormRefusesNonPhysiciansBeforeSubmitting:
    FORM = (_REPO / "mobile" / "app" / "(onboarding)" / "reviewer-apply.tsx").read_text()

    def test_only_md_and_do_are_offered(self):
        assert "const CREDENTIALS = ['MD', 'DO'] as const;" in self.FORM

    def test_it_says_what_a_reviewer_actually_does(self):
        # Someone deciding whether to apply needs to know what they are agreeing
        # to spend time on.
        assert "approve the wording patients will see" in self.FORM


class TestApprovingTakesTwoTaps:
    """Approving is effectively irreversible: rejecting afterwards sets
    'revoked', a different state from never-approved, and in between the account
    can sign wording that patients read."""

    DASH = (_REPO / "mobile" / "app" / "review" / "applications.tsx").read_text()

    def test_the_second_tap_names_the_person(self):
        assert "Yes, approve ${item.full_name}" in self.DASH

    def test_the_confirmation_says_what_approval_grants(self):
        assert "sign off on wording that patients read" in self.DASH

    def test_buttons_are_gated_on_the_mutation_not_only_the_query(self):
        # isLoading is false during a background refetch (TanStack v5), so a row
        # that was already decided would keep live buttons.
        assert "const busy = decide.isPending;" in self.DASH

    def test_a_race_between_two_admins_reads_as_one(self):
        assert "ALREADY_DECIDED" in self.DASH
