"""
Reconcile-matrix unit tests for the patient belief store (pure — no network,
no Supabase, no LLM). Covers the decision table in lib/patient_model.py:

  prior state x candidate (confidence / stakes / explicitness / polarity)
  -> ADD | UPDATE | INVALIDATE | NOOP | PENDING_CONFIRMATION

plus materialization semantics (lists merge, treatments never deleted) and
pending-queue hygiene (cap, replace-per-path, expiry).

Run: python3 -m pytest tests/test_reconcile.py -v
"""

import os
import sys
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "lib"))

from patient_model import (  # noqa: E402
    CandidateFact,
    ReconcileDecision,
    _expire_pending,
    _materialize,
    ensure_beliefs,
    is_high_stakes,
    reconcile,
)


def belief(value, status="provisional", confidence=0.6, source="chat"):
    return {
        "value": value, "confidence": confidence, "status": status,
        "source": source, "session_id": None,
        "first_observed": "2026-07-01T00:00:00Z",
        "last_updated": "2026-07-01T00:00:00Z", "history": [],
    }


def beliefs_with(fields):
    return {"version": 1, "fields": fields, "pending": []}


def one(candidates, beliefs):
    decisions = reconcile(candidates, beliefs)
    assert len(decisions) == 1
    return decisions[0]


# ---------------------------------------------------------------- stakes map

def test_high_stakes_paths():
    assert is_high_stakes("primaryDiagnosis.stage")
    assert is_high_stakes("primaryDiagnosis.biomarkers.KRAS")
    assert is_high_stakes("treatments.folfox")
    assert is_high_stakes("patient.comorbidities.diabetes")
    assert not is_high_stakes("patient.age")
    assert not is_high_stakes("patient.zipCode")
    assert not is_high_stakes("symptoms.fatigue")


# ------------------------------------------------------------- no prior fact

def test_add_low_stakes_no_prior():
    d = one([CandidateFact("patient.age", 62, 0.7, "chat_llm")], beliefs_with({}))
    assert d.action == "ADD" and d.reason == "no_prior"


def test_low_confidence_skipped():
    d = one([CandidateFact("patient.age", 62, 0.4, "chat_llm")], beliefs_with({}))
    assert d.action == "NOOP" and d.reason == "low_confidence_skip"


def test_high_stakes_new_from_llm_goes_pending():
    d = one([CandidateFact("primaryDiagnosis.stage", "Stage IV", 0.8, "chat_llm")],
            beliefs_with({}))
    assert d.action == "PENDING_CONFIRMATION" and d.reason == "high_stakes_new"


def test_high_stakes_new_from_explicit_regex_commits():
    d = one([CandidateFact("primaryDiagnosis.stage", "Stage III", 0.95, "chat_regex")],
            beliefs_with({}))
    assert d.action == "ADD"


# ------------------------------------------------------------- same value

def test_same_value_reinforces():
    b = beliefs_with({"patient.age": belief(62)})
    d = one([CandidateFact("patient.age", 62, 0.8, "chat_llm")], b)
    assert d.action == "NOOP" and d.reason == "reinforces_existing"


def test_same_value_case_insensitive():
    b = beliefs_with({"primaryDiagnosis.stage": belief("Stage III", status="confirmed")})
    d = one([CandidateFact("primaryDiagnosis.stage", "stage iii", 0.8, "chat_llm")], b)
    assert d.action == "NOOP" and d.reason == "reinforces_existing"


# ------------------------------------------------------------- conflicts

def test_provisional_conflict_updates_when_confident():
    b = beliefs_with({"patient.zipCode": belief("94110", confidence=0.6)})
    d = one([CandidateFact("patient.zipCode", "94117", 0.95, "chat_regex")], b)
    assert d.action == "UPDATE" and d.old_value == "94110"


def test_provisional_conflict_weaker_evidence_noop():
    b = beliefs_with({"patient.age": belief(62, confidence=0.9)})
    d = one([CandidateFact("patient.age", 65, 0.5, "chat_llm")], b)
    assert d.action == "NOOP" and d.reason == "lower_confidence_conflict"


def test_confirmed_high_stakes_conflict_never_silent():
    b = beliefs_with({"primaryDiagnosis.stage": belief("Stage III", status="confirmed", confidence=1.0)})
    # Even an explicit regex assertion must not silently overwrite a confirmed stage.
    d = one([CandidateFact("primaryDiagnosis.stage", "Stage IV", 0.95, "chat_regex")], b)
    assert d.action == "PENDING_CONFIRMATION"
    assert d.reason == "conflicts_confirmed_high_stakes"


def test_confirmed_low_stakes_explicit_change_updates():
    b = beliefs_with({"patient.zipCode": belief("94110", status="confirmed", confidence=1.0)})
    d = one([CandidateFact("patient.zipCode", "10029", 0.95, "chat_regex")], b)
    assert d.action == "UPDATE" and d.reason == "explicit_user_change"


def test_confirmed_low_stakes_implicit_change_goes_pending():
    b = beliefs_with({"patient.zipCode": belief("94110", status="confirmed", confidence=1.0)})
    d = one([CandidateFact("patient.zipCode", "10029", 0.7, "chat_llm")], b)
    assert d.action == "PENDING_CONFIRMATION" and d.reason == "conflicts_confirmed"


def test_high_stakes_provisional_change_from_llm_goes_pending():
    b = beliefs_with({"primaryDiagnosis.biomarkers.KRAS": belief("wild-type")})
    d = one([CandidateFact("primaryDiagnosis.biomarkers.KRAS", "G12D", 0.8, "chat_llm")], b)
    assert d.action == "PENDING_CONFIRMATION" and d.reason == "high_stakes_change"


# ------------------------------------------------------------- negation

def test_negation_invalidates():
    b = beliefs_with({"treatments.folfox": belief({"regimen": "FOLFOX", "status": "active"})})
    d = one([CandidateFact("treatments.folfox", {"regimen": "FOLFOX"}, 0.8, "chat_llm",
                           polarity="negate")], b)
    assert d.action == "INVALIDATE" and d.reason == "negation"


def test_negation_without_prior_noop():
    d = one([CandidateFact("symptoms.nausea", "nausea", 0.8, "chat_llm", polarity="negate")],
            beliefs_with({}))
    assert d.action == "NOOP" and d.reason == "negation_without_prior"


# ------------------------------------------------------------- materialization

def test_materialize_scalar_dotted_path():
    profile = {}
    _materialize(profile, "primaryDiagnosis.biomarkers.KRAS", "G12D")
    assert profile["primaryDiagnosis"]["biomarkers"]["KRAS"] == "G12D"


def test_materialize_treatment_merges_by_identity():
    profile = {"treatments": [{"regimen": "FOLFOX", "status": "active"}]}
    _materialize(profile, "treatments.folfox", {"regimen": "FOLFOX", "status": "completed"})
    assert len(profile["treatments"]) == 1
    assert profile["treatments"][0]["status"] == "completed"


def test_materialize_treatment_invalidate_marks_completed_never_deletes():
    profile = {"treatments": [{"regimen": "FOLFOX", "status": "active"}]}
    _materialize(profile, "treatments.folfox", None, invalidate=True)
    assert len(profile["treatments"]) == 1
    assert profile["treatments"][0]["status"] == "completed"


def test_materialize_symptom_appends_once():
    profile = {"symptoms": ["fatigue"]}
    _materialize(profile, "symptoms.fatigue", "fatigue")
    _materialize(profile, "symptoms.nausea", "nausea")
    assert profile["symptoms"] == ["fatigue", "nausea"]


def test_materialize_symptom_invalidate_removes_from_list():
    profile = {"symptoms": ["fatigue", "nausea"]}
    _materialize(profile, "symptoms.nausea", None, invalidate=True)
    assert profile["symptoms"] == ["fatigue"]


# ------------------------------------------------------------- pending hygiene

def test_expire_pending_by_attempts_and_age():
    old = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"
    fresh = datetime.utcnow().isoformat() + "Z"
    b = {"version": 1, "fields": {}, "pending": [
        {"id": "a", "path": "p1", "attempts": 3, "created_at": fresh},   # too many asks
        {"id": "b", "path": "p2", "attempts": 0, "created_at": old},     # too old
        {"id": "c", "path": "p3", "attempts": 1, "created_at": fresh},   # alive
    ]}
    _expire_pending(b, fresh)
    assert [p["id"] for p in b["pending"]] == ["c"]


def test_ensure_beliefs_shape():
    profile = {}
    b = ensure_beliefs(profile)
    assert b["version"] == 1 and b["fields"] == {} and b["pending"] == []
    assert profile["beliefs"] is b
