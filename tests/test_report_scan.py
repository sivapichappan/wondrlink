# test_report_scan.py
"""
Report scan: de-identification unit tests + Flask endpoint tests.

The de-id enforcement test (the LLM mock must never see Patient:/DOB:/MRN
content) is the release gate for the privacy claim: only de-identified text
reaches the extractor.
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
from deidentify import (  # noqa: E402
    deidentify_report_text, detect_pii_leaks, report_name_mismatch,
)
from patient_model import validate_report_fact, apply_confirmed_facts  # noqa: E402

TEST_USER = {"user_id": "00000000-0000-4000-8000-000000000003"}
AUTH = {"Authorization": "Bearer test-token", "Content-Type": "application/json"}

REPORT_FIXTURE = """SURGICAL PATHOLOGY REPORT
Patient Name: Rosa Martinez
DOB: 03/14/1961
MRN: 8842197
Accession #: SP-26-10442
Specimen: right colon, hemicolectomy

DIAGNOSIS:
Adenocarcinoma of the ascending colon, moderately differentiated.
Tumor invades through the muscularis propria (pT3).
4 of 21 regional lymph nodes positive (pN1). Stage III.

MOLECULAR FINDINGS:
KRAS G12C mutation detected.
BRAF: wild-type. MSI status: MSS (microsatellite stable).
CEA 12.4 ng/mL.
"""


class TestDeidentifyReportText:
    def test_header_identifier_lines_dropped(self):
        out = deidentify_report_text(REPORT_FIXTURE)
        assert "Rosa Martinez" not in out
        assert "03/14/1961" not in out
        assert "8842197" not in out
        assert "SP-26-10442" not in out

    def test_clinical_content_survives(self):
        out = deidentify_report_text(REPORT_FIXTURE)
        assert "KRAS G12C mutation detected" in out
        assert "Stage III" in out
        assert "Adenocarcinoma" in out
        assert "CEA 12.4" in out

    def test_profile_identifiers_stripped(self):
        text = "Findings discussed with Rosa on follow-up. Tumor in ascending colon."
        profile = {"patient": {"firstName": "Rosa", "zipCode": "07030"}}
        out = deidentify_report_text(text, profile)
        assert "Rosa" not in out
        assert "ascending colon" in out

    def test_guard_clean_after_scrub(self):
        out = deidentify_report_text(REPORT_FIXTURE)
        leaks = [(n, s) for n, s in detect_pii_leaks(out)
                 if not n.startswith("full_date")]
        assert leaks == []

    def test_empty_text(self):
        assert deidentify_report_text("") == ""

    def test_tumor_measurements_are_not_street_addresses(self):
        """"N cm in greatest dimension" is boilerplate in every pathology
        report, and it used to trip the guard's street-address pattern:
        with \\s* between the street-name words, "greatest" split into
        "greate" + "st". That 422'd the scan of the exact document this
        feature exists to read. Locks the \\s+ separator."""
        for phrase in ("Mass measuring 2.6 cm in greatest dimension.",
                       "Lesion 1.4 cm in greatest diameter, grade 2.",
                       "Dose 4256 cGy in 16 fractions to the left breast."):
            leaks = [n for n, _ in detect_pii_leaks(phrase) if n == "street_address"]
            assert leaks == [], f"false positive on {phrase!r}"

    def test_real_street_addresses_still_caught(self):
        """The other half: narrowing the separator must not open a hole."""
        for address in ("Seen at 1515 Holcombe Boulevard for infusion.",
                        "Clinic moved to 123 Main St last spring.",
                        "Records sent to 456 Oak Avenue."):
            leaks = [n for n, _ in detect_pii_leaks(address) if n == "street_address"]
            assert leaks == ["street_address"], f"missed address in {address!r}"


class TestReportNameMismatch:
    """Warn-never-block: True only on a clear mismatch; every doubt is False."""

    def test_exact_match_false(self):
        assert report_name_mismatch(
            REPORT_FIXTURE, {"patient": {"firstName": "Rosa"}}) is False

    def test_last_first_ordering_false(self):
        assert report_name_mismatch(
            "Patient: MARTINEZ, ROSA\nDIAGNOSIS: colon adenocarcinoma",
            {"patient": {"firstName": "Rosa"}}) is False

    def test_middle_initial_false(self):
        assert report_name_mismatch(
            "Name: Rosa M. Martinez\nDIAGNOSIS follows.",
            {"patient": {"firstName": "Rosa"}}) is False

    def test_nickname_prefix_false(self):
        assert report_name_mismatch(
            "Patient Name: Rob Smith\nDIAGNOSIS follows.",
            {"patient": {"firstName": "Robert"}}) is False

    def test_true_mismatch(self):
        assert report_name_mismatch(
            REPORT_FIXTURE, {"patient": {"firstName": "Amara"}}) is True

    def test_legacy_full_name_key(self):
        assert report_name_mismatch(
            "Name: MARTINEZ, ROSA\nDIAGNOSIS follows.",
            {"patient": {"name": "Rosa Martinez"}}) is False

    def test_no_profile_name_never_warns(self):
        for profile in (None, {}, {"patient": {}},
                        {"patient": {"firstName": "unknown"}}):
            assert report_name_mismatch(REPORT_FIXTURE, profile) is False

    def test_no_name_line_never_warns(self):
        text = "DIAGNOSIS:\nAdenocarcinoma of the colon. Stage III.\nKRAS G12C."
        assert report_name_mismatch(
            text, {"patient": {"firstName": "Rosa"}}) is False

    def test_provider_lines_ignored(self):
        text = ("Ordering Physician: Dr. A. Placeholder, MD\n"
                "Electronically signed: Dr. B. Sample\n"
                "Inpatient: yes\n"
                "DIAGNOSIS: colon adenocarcinoma.")
        assert report_name_mismatch(
            text, {"patient": {"firstName": "Rosa"}}) is False

    def test_caregiver_holder_name_ignored(self):
        # patient.* is the care recipient; the account holder's own name must
        # not create overlap — a caregiver scanning THEIR report should warn.
        profile = {"patient": {"firstName": "Rosa"},
                   "account_holder_name": "John"}
        assert report_name_mismatch(
            "Patient Name: John Doe\nDIAGNOSIS follows.", profile) is True

    def test_empty_text_false(self):
        assert report_name_mismatch("", {"patient": {"firstName": "Rosa"}}) is False


class TestValidateReportFact:
    def test_valid_facts(self):
        assert validate_report_fact("primaryDiagnosis.stage", "Stage III") is not None
        assert validate_report_fact("primaryDiagnosis.biomarkers.kras", "G12C")[0] == \
            "primaryDiagnosis.biomarkers.KRAS"
        path, value = validate_report_fact(
            "treatments.folfox", {"regimen": "FOLFOX", "status": "active"})
        assert path == "treatments.folfox" and value["regimen"] == "FOLFOX"

    def test_invalid_facts(self):
        assert validate_report_fact("primaryDiagnosis.stage", "Stage 9") is None
        assert validate_report_fact("labs.cea", "12.4") is None
        assert validate_report_fact("primaryDiagnosis.biomarkers.FAKE", "positive") is None
        assert validate_report_fact("patient.firstName", "Rosa") is None
        assert validate_report_fact("treatments.x", {"no_regimen": True}) is None


@pytest.fixture()
def client():
    index.app.config["TESTING"] = True
    with index.app.test_client() as c:
        yield c


@pytest.fixture()
def authed():
    with patch.object(index, "verify_token", return_value=TEST_USER), \
         patch("rate_limit.check_rate_limit", return_value=(True, 99)), \
         patch.object(index, "load_profile", return_value={}), \
         patch("supabase_storage.get_cancer_slug", return_value="colorectal"), \
         patch("supabase_storage.append_patient_event", return_value=True):
        yield


FINDINGS = {"findings": [{"path": "primaryDiagnosis.biomarkers.KRAS",
                          "label": "KRAS biomarker result", "value": "G12C",
                          "confidence": 0.9, "evidence": "KRAS G12C mutation detected"}],
            "display_only": [{"label": "CEA", "value": "12.4 ng/mL"}]}


class TestExtractEndpoint:
    def test_deid_enforcement_release_gate(self, client, authed):
        """THE privacy gate: the extractor mock must never receive the
        identifiers present in the raw fixture."""
        captured = {}

        def _mock_extract(deid_text, cancer_kind):
            captured["text"] = deid_text
            return FINDINGS

        with patch("patient_model.extract_report_findings", side_effect=_mock_extract):
            resp = client.post("/api/report/extract", headers=AUTH,
                               data=json.dumps({"text": REPORT_FIXTURE,
                                                "source_type": "image"}))
        assert resp.status_code == 200
        assert "Rosa Martinez" not in captured["text"]
        assert "8842197" not in captured["text"]
        assert "03/14/1961" not in captured["text"]
        assert "KRAS G12C" in captured["text"]
        body = resp.get_json()
        assert body["findings"][0]["path"] == "primaryDiagnosis.biomarkers.KRAS"

    def test_pii_guard_aborts(self, client, authed):
        # A labeled insurance member ID is a pattern the scrubber does NOT
        # remove but the guard DOES catch -> 422, extractor never called.
        # (SSNs/phones/emails are scrubbed upstream, so they can't be the
        # fixture here — the guard is the second line of defense.)
        text = ("Colon adenocarcinoma discussed at tumor board. " * 3 +
                "Insurance member ID: ZX99182734 on file.")
        with patch("patient_model.extract_report_findings") as gen:
            resp = client.post("/api/report/extract", headers=AUTH,
                               data=json.dumps({"text": text, "source_type": "image"}))
        assert resp.status_code == 422
        assert resp.get_json()["error"] == "pii_guard"
        gen.assert_not_called()

    def test_short_text_422(self, client, authed):
        resp = client.post("/api/report/extract", headers=AUTH,
                           data=json.dumps({"text": "too short", "source_type": "image"}))
        assert resp.status_code == 422
        assert resp.get_json()["error"] == "empty_text"

    def test_name_mismatch_flag_and_no_echo(self, client, authed):
        with patch.object(index, "load_profile",
                          return_value={"patient": {"firstName": "Amara"}}), \
             patch("patient_model.extract_report_findings", return_value=FINDINGS):
            resp = client.post("/api/report/extract", headers=AUTH,
                               data=json.dumps({"text": REPORT_FIXTURE,
                                                "source_type": "image"}))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["name_mismatch"] is True
        # Warn-never-block: findings are intact.
        assert body["findings"][0]["path"] == "primaryDiagnosis.biomarkers.KRAS"
        # The boolean is the ONLY output — no name ever echoes back.
        raw = resp.get_data(as_text=True)
        for name in ("Rosa", "Martinez", "Amara"):
            assert name not in raw

    def test_name_match_flag_false(self, client, authed):
        captured = {}

        def _mock_extract(deid_text, cancer_kind):
            captured["text"] = deid_text
            return FINDINGS

        with patch.object(index, "load_profile",
                          return_value={"patient": {"firstName": "Rosa"}}), \
             patch("patient_model.extract_report_findings", side_effect=_mock_extract):
            resp = client.post("/api/report/extract", headers=AUTH,
                               data=json.dumps({"text": REPORT_FIXTURE,
                                                "source_type": "image"}))
        assert resp.status_code == 200
        assert resp.get_json()["name_mismatch"] is False
        # The pre-deid read must not weaken the release gate.
        assert "Rosa" not in captured["text"]

    def test_no_profile_no_flag(self, client, authed):
        with patch("patient_model.extract_report_findings", return_value=FINDINGS):
            resp = client.post("/api/report/extract", headers=AUTH,
                               data=json.dumps({"text": REPORT_FIXTURE,
                                                "source_type": "image"}))
        assert resp.status_code == 200
        assert resp.get_json()["name_mismatch"] is False

        # A broken profile load must never break a scan.
        with patch.object(index, "load_profile", side_effect=Exception("boom")), \
             patch("patient_model.extract_report_findings", return_value=FINDINGS):
            resp = client.post("/api/report/extract", headers=AUTH,
                               data=json.dumps({"text": REPORT_FIXTURE,
                                                "source_type": "image"}))
        assert resp.status_code == 200
        assert resp.get_json()["name_mismatch"] is False

    def test_event_payload_has_flag(self, client, authed):
        events = []

        def _capture_event(user_id, kind, payload=None, source=None):
            events.append(payload or {})
            return True

        with patch.object(index, "load_profile",
                          return_value={"patient": {"firstName": "Amara"}}), \
             patch("supabase_storage.append_patient_event",
                   side_effect=_capture_event), \
             patch("patient_model.extract_report_findings", return_value=FINDINGS):
            resp = client.post("/api/report/extract", headers=AUTH,
                               data=json.dumps({"text": REPORT_FIXTURE,
                                                "source_type": "image"}))
        assert resp.status_code == 200
        assert len(events) == 1
        assert events[0]["name_mismatch"] is True
        # Counts and booleans only — nothing name-like in the event payload.
        assert all(isinstance(v, (int, bool, str)) for v in events[0].values())
        joined = json.dumps(events[0])
        for name in ("Rosa", "Martinez", "Amara"):
            assert name not in joined

    def test_requires_auth(self, client):
        resp = client.post("/api/report/extract",
                           headers={"Content-Type": "application/json"},
                           data=json.dumps({"text": "x" * 100}))
        assert resp.status_code == 401


class TestApplyEndpoint:
    def test_happy_path_writes_confirmed_beliefs(self, client, authed):
        saved = {}

        def _mock_save(user_id, profile):
            saved["profile"] = profile
            return True

        with patch.object(index, "save_profile", side_effect=_mock_save):
            resp = client.post("/api/report/apply", headers=AUTH,
                               data=json.dumps({"facts": [
                                   {"path": "primaryDiagnosis.biomarkers.KRAS", "value": "G12C"},
                                   {"path": "primaryDiagnosis.stage", "value": "Stage III"},
                               ]}))
        assert resp.status_code == 200
        assert resp.get_json()["applied"] == 2
        beliefs = saved["profile"]["beliefs"]["fields"]
        kras = beliefs["primaryDiagnosis.biomarkers.KRAS"]
        assert kras["status"] == "confirmed"
        assert kras["source"] == "report"
        # materialized into the canonical profile shape too
        assert saved["profile"]["primaryDiagnosis"]["biomarkers"]["KRAS"] == "G12C"

    def test_rejects_unknown_paths_all_or_nothing(self, client, authed):
        with patch.object(index, "save_profile") as save:
            resp = client.post("/api/report/apply", headers=AUTH,
                               data=json.dumps({"facts": [
                                   {"path": "primaryDiagnosis.stage", "value": "Stage III"},
                                   {"path": "labs.cea", "value": "12.4"},
                               ]}))
        assert resp.status_code == 400
        assert "labs.cea" in resp.get_json()["rejected_paths"]
        save.assert_not_called()

    def test_empty_batch_400(self, client, authed):
        resp = client.post("/api/report/apply", headers=AUTH,
                           data=json.dumps({"facts": []}))
        assert resp.status_code == 400

    def test_requires_auth(self, client):
        resp = client.post("/api/report/apply",
                           headers={"Content-Type": "application/json"},
                           data=json.dumps({"facts": [{"path": "x", "value": "y"}]}))
        assert resp.status_code == 401
