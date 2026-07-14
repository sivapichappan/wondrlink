#!/usr/bin/env python3
"""
Patient-model integration tests (offline — Supabase stubbed, no LLM).

Exercises the LIVE (non-shadow) belief pipeline end-to-end in memory:
  apply_decisions  -> beliefs + materialized profile + pending queue + events
  confirm_belief   -> accept commits/materializes; deny drops + asks back
  absorb_form_profile / carry_over_app_state -> the wizard-save path

Run: python3 scripts/test_patient_model.py
"""

import os
import sys
from typing import List

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'lib'))

import supabase_storage  # noqa: E402
import patient_model as pm  # noqa: E402

FAILURES: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


# ---------------------------------------------------------------- stubs
EVENTS: List[dict] = []
SAVED: List[dict] = []
_PROFILE_DB: dict = {}


def _stub_append_event(user_id, kind, path=None, payload=None, source='system',
                       session_id=None, occurred_at=None):
    EVENTS.append({"kind": kind, "path": path, "payload": payload, "source": source})
    return True


def _stub_save_profile(user_id, profile):
    SAVED.append(profile)
    _PROFILE_DB[user_id] = profile
    return True


def _stub_load_profile(user_id):
    return _PROFILE_DB.get(user_id)


supabase_storage.append_patient_event = _stub_append_event
supabase_storage.save_profile = _stub_save_profile
supabase_storage.load_profile = _stub_load_profile


def test_live_apply_pipeline():
    print("\n1. Live apply: commit, pend, invalidate")
    EVENTS.clear(); SAVED.clear()
    profile = {"patient": {}, "treatments": [{"regimen": "FOLFOX", "status": "active"}]}
    # Mirrors the route: lazy-sync gives legacy materialized fields a belief
    # prior, so the FOLFOX negation below has something to invalidate.
    pm.absorb_form_profile(profile, only_missing=True)
    check("lazy-sync created a belief for the legacy treatment",
          "treatments.folfox" in profile["beliefs"]["fields"])
    decisions = pm.reconcile([
        pm.CandidateFact("patient.age", "62", 0.95, "chat_regex"),                       # low-stakes -> commit
        pm.CandidateFact("primaryDiagnosis.biomarkers.KRAS", "G12D", 0.8, "chat_llm"),   # high-stakes -> pending
        pm.CandidateFact("treatments.folfox", {"regimen": "FOLFOX"}, 0.8, "chat_llm",
                         polarity="negate"),                                             # negation -> invalidate
    ], profile["beliefs"])
    res = pm.apply_decisions("user-1", profile, decisions, session_id="s1", shadow=False)

    check("age committed as provisional belief",
          profile["beliefs"]["fields"].get("patient.age", {}).get("status") == "provisional")
    check("age materialized into profile", profile["patient"].get("age") == "62")
    check("KRAS went to pending, NOT materialized",
          len(res.pending_confirmations) == 1 and
          "biomarkers" not in (profile.get("primaryDiagnosis") or {}))
    check("pending carries a human prompt", "KRAS" in res.pending_confirmations[0]["prompt"])
    check("FOLFOX invalidated -> status completed, record kept",
          profile["treatments"][0]["status"] == "completed" and len(profile["treatments"]) == 1)
    check("events written (add + pending + invalidate)",
          {e["kind"] for e in EVENTS} >= {"belief_add", "pending_created", "belief_invalidate"})
    check("profile saved once", len(SAVED) == 1)


def test_confirm_accept_roundtrip():
    print("\n2. Confirm chip: accept")
    EVENTS.clear()
    profile = _PROFILE_DB["user-1"]
    pending_id = profile["beliefs"]["pending"][0]["id"]
    out = pm.confirm_belief("user-1", pending_id, accept=True)
    check("status confirmed", out.get("status") == "confirmed")
    belief = profile["beliefs"]["fields"].get("primaryDiagnosis.biomarkers.KRAS", {})
    check("belief now confirmed with boosted confidence",
          belief.get("status") == "confirmed" and belief.get("confidence", 0) >= 0.9)
    check("value materialized on accept",
          profile.get("primaryDiagnosis", {}).get("biomarkers", {}).get("KRAS") == "G12D")
    check("pending queue drained", profile["beliefs"]["pending"] == [])
    check("belief_confirm event written", any(e["kind"] == "belief_confirm" for e in EVENTS))


def test_confirm_deny_roundtrip():
    print("\n3. Confirm chip: deny")
    EVENTS.clear()
    profile = _PROFILE_DB["user-1"]
    decisions = pm.reconcile(
        [pm.CandidateFact("primaryDiagnosis.stage", "Stage IV", 0.8, "chat_llm")],
        profile["beliefs"])
    pm.apply_decisions("user-1", profile, decisions, shadow=False)
    pending_id = profile["beliefs"]["pending"][0]["id"]
    out = pm.confirm_belief("user-1", pending_id, accept=False)
    check("status rejected", out.get("status") == "rejected")
    check("corrected question offered", "correct" in (out.get("corrected_question") or ""))
    check("stage NOT materialized on deny",
          (profile.get("primaryDiagnosis") or {}).get("stage") != "Stage IV")
    check("belief_reject event written", any(e["kind"] == "belief_reject" for e in EVENTS))
    check("unknown id -> not_found",
          pm.confirm_belief("user-1", "conf_nope", True).get("status") == "not_found")


def test_pending_queue_hygiene():
    print("\n4. Pending queue: replace per path + cap")
    profile = {"patient": {}}
    pm.ensure_beliefs(profile)
    for value, marker in (("Stage III", "A"), ("Stage IV", "B")):
        decisions = pm.reconcile(
            [pm.CandidateFact("primaryDiagnosis.stage", value, 0.8, "chat_llm")],
            profile["beliefs"])
        pm.apply_decisions("user-2", profile, decisions, shadow=False)
    pending = profile["beliefs"]["pending"]
    check("same path replaced, not duplicated",
          len(pending) == 1 and pending[0]["proposed_value"] == "Stage IV")

    for i, path in enumerate(["primaryDiagnosis.histology",
                              "primaryDiagnosis.biomarkers.KRAS",
                              "primaryDiagnosis.biomarkers.MSI",
                              "primaryDiagnosis.biomarkers.HER2"]):
        decisions = pm.reconcile(
            [pm.CandidateFact(path, f"v{i}", 0.8, "chat_llm")], profile["beliefs"])
        pm.apply_decisions("user-2", profile, decisions, shadow=False)
    check("queue capped at 3", len(profile["beliefs"]["pending"]) <= 3)


def test_form_absorption():
    print("\n5. Wizard path: absorb + carry-over")
    incoming = {
        "patient": {"firstName": "Maria", "age": 55, "sex": "Female", "comorbidities": ["hypertension"]},
        "primaryDiagnosis": {"site": "colon", "stage": "Stage II", "biomarkers": {"KRAS": "wild-type"}},
        "treatments": [{"regimen": "CAPOX", "status": "active"}],
        "symptoms": ["fatigue"],
    }
    n = pm.absorb_form_profile(incoming)
    fields = incoming["beliefs"]["fields"]
    check("form fields absorbed as confirmed", n >= 8 and
          fields["primaryDiagnosis.stage"]["status"] == "confirmed" and
          fields["primaryDiagnosis.stage"]["source"] == "form")
    check("treatment belief keyed by slug", "treatments.capox" in fields)

    # Re-upload with a changed stage -> history entry, still confirmed
    incoming["primaryDiagnosis"]["stage"] = "Stage III"
    pm.absorb_form_profile(incoming)
    stage = fields["primaryDiagnosis.stage"]
    check("form re-save records history on change",
          stage["value"] == "Stage III" and stage["history"] and
          stage["history"][0]["value"] == "Stage II")

    existing = {"beliefs": incoming["beliefs"], "visit_recaps": [{"timestamp": "t"}],
                "model_state": {"turns_since_question": 2}}
    fresh_upload = {"patient": {"firstName": "Maria"}}
    merged = pm.carry_over_app_state(fresh_upload, existing)
    check("upload carries over beliefs/model_state/visit_recaps",
          "beliefs" in merged and "model_state" in merged and "visit_recaps" in merged)


def test_dormant_learning_loop_parity():
    print("\n6. Dormant learning loop: flag off => byte-identical consent behavior")

    class _FakeResp:
        data: list = []

    class _FakeTable:
        def select(self, *_a, **_k): return self
        def eq(self, *_a, **_k): return self
        def order(self, *_a, **_k): return self
        def execute(self): return _FakeResp()

    class _FakeClient:
        def table(self, *_a, **_k): return _FakeTable()

    real_get_admin = supabase_storage.get_admin_client
    supabase_storage.get_admin_client = lambda: _FakeClient()
    try:
        os.environ.pop("FEATURE_MODEL_IMPROVEMENT", None)
        status_off = supabase_storage.get_consent_status("user-x")
        check("flag off: legacy keys only",
              set(status_off.keys()) ==
              {"consent_collection", "consent_sharing", "consent_terms", "chat_disabled"})
        check("flag off: opt-in key unrecordable",
              supabase_storage.record_consent_action("user-x", "consent_model_improvement", "grant") is False)

        import learning_loop
        check("flag off: emitter is a hard no-op",
              learning_loop.emit_pattern_record("user-x", {"cancer_slug": "colorectal", "topic": "t"}) is False)

        os.environ["FEATURE_MODEL_IMPROVEMENT"] = "true"
        status_on = supabase_storage.get_consent_status("user-x")
        check("flag on: opt-in key appears, default NOT granted",
              status_on.get("consent_model_improvement", {}).get("granted") is False)
        check("flag on: opt-in never affects chat_disabled",
              status_on["chat_disabled"] is False)
    finally:
        os.environ.pop("FEATURE_MODEL_IMPROVEMENT", None)
        supabase_storage.get_admin_client = real_get_admin


if __name__ == '__main__':
    print("Patient-model integration tests (offline)")
    print("=" * 60)
    test_live_apply_pipeline()
    test_confirm_accept_roundtrip()
    test_confirm_deny_roundtrip()
    test_pending_queue_hygiene()
    test_form_absorption()
    test_dormant_learning_loop_parity()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"RESULT: {len(FAILURES)} FAILURE(S): {FAILURES}")
        sys.exit(1)
    print("RESULT: ALL PASS")
