"""
Modeler engine unit tests (pure — no network, no Supabase, no LLM).

Covers lib/modeler.py against the golden fixture:
  parse   strict item-wise validation (evidence resolution, enums, windows,
          timing-needs-treatment-evidence, prognosis ban, no corroborated minting)
  merge   edge identity/strength/status transitions, cap-50 pruning
  calib   deterministic matcher, verified LLM resolutions, expiry, counters
  codec   day-offset window round-trip
  run     watermark advances on success, held on failure (stubbed orchestrator)
  refl    reflections -> pending queue (force-pending, cap respected)

Run: python3 -m pytest tests/test_modeler.py -v
"""

import copy
import json
import os
import sys
from datetime import datetime, timedelta

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "lib"))

import modeler  # noqa: E402
from modeler import (  # noqa: E402
    EDGE_CAP,
    absolutize_window,
    check_expectations,
    ensure_connections,
    merge_graph,
    parse_modeler_output,
    relativize,
    should_run,
    store_reflections,
)

NOW = datetime(2026, 7, 14, 12, 0, 0)

with open(os.path.join(REPO_ROOT, "tests", "fixtures", "modeler_golden.json")) as f:
    GOLDEN = json.load(f)

INDEX = set(GOLDEN["index"])
EVENTS = GOLDEN["events"]
CHUNKS = GOLDEN["chunks"]


def golden_output():
    return copy.deepcopy(GOLDEN["output"])


def fresh_connections():
    return ensure_connections({})


# ---------------------------------------------------------------- parse

class TestParse:
    def test_golden_fixture_fully_accepted(self):
        ops, rejects = parse_modeler_output(golden_output(), INDEX)
        assert len(ops["edges"]) == 2
        assert len(ops["expectations_open"]) == 1
        assert len(ops["reflections"]) == 1
        assert sum(rejects.values()) == 0

    def test_non_dict_yields_empty(self):
        ops, _ = parse_modeler_output("not json at all", INDEX)
        assert sum(len(v) for v in ops.values()) == 0

    def test_missing_evidence_rejected(self):
        out = golden_output()
        out["edges"][0]["evidence"] = []
        ops, rejects = parse_modeler_output(out, INDEX)
        assert len(ops["edges"]) == 1 and rejects["edges"] == 1

    def test_unresolvable_evidence_ref_rejected(self):
        out = golden_output()
        out["edges"][0]["evidence"][0]["ref"] = "E99"
        ops, rejects = parse_modeler_output(out, INDEX)
        assert len(ops["edges"]) == 1 and rejects["edges"] == 1

    def test_bad_rel_enum_rejected(self):
        out = golden_output()
        out["edges"][0]["rel"] = "cures"
        ops, rejects = parse_modeler_output(out, INDEX)
        assert rejects["edges"] == 1

    def test_model_cannot_mint_corroborated(self):
        out = golden_output()
        out["edges"][0]["status"] = "corroborated"
        ops, rejects = parse_modeler_output(out, INDEX)
        assert rejects["edges"] == 1
        assert all(e["status"] != "corroborated" for e in ops["edges"])

    def test_window_over_180_days_rejected(self):
        out = golden_output()
        out["expectations"]["open"][0]["closes_in_days"] = 200
        ops, rejects = parse_modeler_output(out, INDEX)
        assert len(ops["expectations_open"]) == 0 and rejects["expectations"] == 1

    def test_timing_expectation_requires_treatment_evidence(self):
        out = golden_output()
        # Statement mentions cycles but evidence is guideline-only.
        out["expectations"]["open"][0]["evidence"] = [
            {"kind": "guideline", "ref": "G1", "note": "typical timing"}
        ]
        ops, rejects = parse_modeler_output(out, INDEX)
        assert len(ops["expectations_open"]) == 0 and rejects["expectations"] == 1

    def test_prognosis_language_rejected(self):
        out = golden_output()
        out["reflections"][0]["statement"] = "Patient survival is likely under a year"
        ops, rejects = parse_modeler_output(out, INDEX)
        assert len(ops["reflections"]) == 0 and rejects["reflections"] == 1

    def test_resolution_without_event_evidence_rejected(self):
        out = golden_output()
        out["expectations"]["resolve"] = [
            {"id": "exp_x", "outcome": "hit",
             "evidence": [{"kind": "guideline", "ref": "G1", "note": ""}]}
        ]
        ops, rejects = parse_modeler_output(out, INDEX)
        assert len(ops["expectations_resolve"]) == 0 and rejects["resolutions"] == 1

    def test_refuted_requires_event_evidence(self):
        out = golden_output()
        out["edges"][1]["status"] = "refuted"   # its evidence is belief+guideline
        ops, rejects = parse_modeler_output(out, INDEX)
        assert rejects["edges"] == 1


# ---------------------------------------------------------------- merge

class TestMerge:
    def test_new_edges_added_as_hypothesis(self):
        connections = fresh_connections()
        ops, _ = parse_modeler_output(golden_output(), INDEX)
        deltas = merge_graph(connections, ops, EVENTS, CHUNKS, NOW)
        assert deltas["new_edges"] == 2
        assert all(e["status"] == "hypothesis" for e in connections["edges"])
        assert connections["edges"][0]["id"] == "treatments_folfox--causes--symptoms_neuropathy"

    def test_evidence_refs_resolved_to_durable(self):
        connections = fresh_connections()
        ops, _ = parse_modeler_output(golden_output(), INDEX)
        merge_graph(connections, ops, EVENTS, CHUNKS, NOW)
        refs = [ev["ref"] for e in connections["edges"] for ev in e["evidence"]]
        assert "event:belief_add@2026-07-08T10:00:00" in refs
        assert "guideline:NCCN_colon.pdf#chunk12" in refs

    def test_reproposal_blends_strength_and_corroborates(self):
        connections = fresh_connections()
        ops, _ = parse_modeler_output(golden_output(), INDEX)
        merge_graph(connections, ops, EVENTS, CHUNKS, NOW)
        first = connections["edges"][0]["strength"]
        merge_graph(connections, ops, EVENTS, CHUNKS, NOW + timedelta(days=1))
        edge = connections["edges"][0]
        assert edge["times_seen"] == 2
        assert edge["strength"] == pytest.approx(0.7 * first + 0.3 * 0.7, abs=0.001)
        # times_seen>=2 AND evidence spans event+guideline kinds -> corroborated
        assert edge["status"] == "corroborated"

    def test_single_evidence_kind_never_corroborates(self):
        connections = fresh_connections()
        out = golden_output()
        out["edges"] = [out["edges"][0]]
        out["edges"][0]["evidence"] = [out["edges"][0]["evidence"][0]]  # event only
        out["expectations"] = {"open": [], "resolve": []}
        out["reflections"] = []
        ops, _ = parse_modeler_output(out, INDEX)
        merge_graph(connections, ops, EVENTS, CHUNKS, NOW)
        merge_graph(connections, ops, EVENTS, CHUNKS, NOW)
        assert connections["edges"][0]["times_seen"] == 2
        assert connections["edges"][0]["status"] == "hypothesis"

    def test_prune_at_cap_drops_refuted_and_weakest_first(self):
        connections = fresh_connections()
        for i in range(EDGE_CAP):
            connections["edges"].append({
                "id": f"edge-{i}", "src": {}, "rel": "causes", "dst": {},
                "status": "corroborated" if i < 40 else "refuted",
                "strength": 0.5 + (i % 10) / 100.0,
                "evidence": [], "first_seen": "x", "last_updated": "x", "times_seen": 1,
            })
        ops, _ = parse_modeler_output(golden_output(), INDEX)
        merge_graph(connections, ops, EVENTS, CHUNKS, NOW)
        assert len(connections["edges"]) == EDGE_CAP
        statuses = [e["status"] for e in connections["edges"]]
        assert statuses.count("refuted") < 10          # refuted pruned first
        assert any(e["id"].startswith("treatments_folfox") for e in connections["edges"])

    def test_expectations_deduped_by_statement(self):
        connections = fresh_connections()
        ops, _ = parse_modeler_output(golden_output(), INDEX)
        merge_graph(connections, ops, EVENTS, CHUNKS, NOW)
        deltas = merge_graph(connections, ops, EVENTS, CHUNKS, NOW)
        assert deltas["expectations_opened"] == 0
        assert len([x for x in connections["expectations"] if x["status"] == "open"]) == 1


# ---------------------------------------------------------------- calibration

def _open_expectation(connections, opens_days=-5, closes_days=10, check=None):
    connections["expectations"].append({
        "id": "exp_test1", "statement": "test expectation", "basis": "guideline",
        "evidence": [], "status": "open", "created_at": "x",
        "resolved_at": None, "resolution_evidence": None,
        "window": {"opens": (NOW + timedelta(days=opens_days)).isoformat() + "Z",
                   "closes": (NOW + timedelta(days=closes_days)).isoformat() + "Z"},
        "check": check or {},
    })
    return connections["expectations"][-1]


class TestCalibration:
    def test_deterministic_matcher_hit(self):
        connections = fresh_connections()
        _open_expectation(connections, check={
            "kind": "screening_score", "payload_field": "total_score", "op": "gte", "value": 10})
        event = {"kind": "screening_score", "payload": {"total_score": 14},
                 "recorded_at": NOW.isoformat()}
        resolved = check_expectations(connections, [event], [], [event], NOW)
        assert resolved and resolved[0]["outcome"] == "hit"
        assert connections["calibration"]["hits"] == 1
        assert connections["calibration"]["hit_rate"] == 1.0

    def test_matcher_respects_window(self):
        connections = fresh_connections()
        _open_expectation(connections, opens_days=2, closes_days=10,
                          check={"kind": "screening_score"})
        event = {"kind": "screening_score", "payload": {}, "recorded_at": NOW.isoformat()}
        resolved = check_expectations(connections, [event], [], [event], NOW)
        assert resolved == []    # event before window opens

    def test_llm_resolution_verified_in_window(self):
        connections = fresh_connections()
        _open_expectation(connections)
        events = [{"kind": "belief_add", "payload": {}, "recorded_at": NOW.isoformat()}]
        resolutions = [{"id": "exp_test1", "outcome": "miss",
                        "evidence": [{"kind": "event", "ref": "E1", "note": ""}]}]
        resolved = check_expectations(connections, [], resolutions, events, NOW)
        assert resolved and resolved[0]["outcome"] == "miss"
        assert connections["calibration"]["misses"] == 1

    def test_llm_resolution_with_bogus_ref_ignored(self):
        connections = fresh_connections()
        exp = _open_expectation(connections)
        resolutions = [{"id": "exp_test1", "outcome": "hit",
                        "evidence": [{"kind": "event", "ref": "E9", "note": ""}]}]
        check_expectations(connections, [], resolutions, [], NOW)
        assert exp["status"] == "open"     # nothing resolved

    def test_expiry(self):
        connections = fresh_connections()
        exp = _open_expectation(connections, opens_days=-30, closes_days=-1)
        resolved = check_expectations(connections, [], [], [], NOW)
        assert exp["status"] == "expired"
        assert resolved[0]["outcome"] == "expired"
        assert connections["calibration"]["expired"] == 1
        assert connections["calibration"]["hit_rate"] == 0.0


# ---------------------------------------------------------------- codec

class TestWindowCodec:
    def test_absolutize_then_relativize_round_trip(self):
        window = absolutize_window(7, 45, NOW)
        assert relativize(window["opens"], NOW) == "T+7d"
        assert relativize(window["closes"], NOW) == "T+45d"

    def test_relativize_past(self):
        assert relativize((NOW - timedelta(days=12)).isoformat(), NOW) == "T-12d"

    def test_relativize_garbage(self):
        assert relativize("not-a-date", NOW) == "T-?"


# ---------------------------------------------------------------- should_run

class TestShouldRun:
    def test_gates(self):
        connections = fresh_connections()
        assert should_run(connections, 2, NOW) == (False, "min_events")
        assert should_run(connections, 3, NOW) == (True, "due")
        connections["meta"]["last_run_at"] = (NOW - timedelta(minutes=30)).isoformat()
        assert should_run(connections, 5, NOW) == (False, "min_interval")
        connections["meta"]["last_run_at"] = (NOW - timedelta(hours=2)).isoformat()
        connections["meta"]["runs"] = {"date": NOW.strftime("%Y-%m-%d"), "count": 2}
        assert should_run(connections, 5, NOW) == (False, "daily_cap")
        connections["meta"]["runs"] = {"date": "2026-07-13", "count": 2}
        assert should_run(connections, 5, NOW) == (True, "due")


# ---------------------------------------------------------------- orchestrator

class _Stub:
    """Attribute bag for monkeypatching storage."""


@pytest.fixture()
def stubbed_run(monkeypatch):
    """run_for_user with all I/O stubbed; returns (call, state) handles."""
    import supabase_storage

    state = _Stub()
    # Beliefs must exist for belief-path evidence refs to resolve in the index.
    state.profile = {
        "patient": {"age": 62},
        "treatments": [{"regimen": "FOLFOX", "status": "active"}],
        "beliefs": {"version": 1, "pending": [], "fields": {
            "treatments.folfox": {"value": {"regimen": "FOLFOX"}, "confidence": 1.0,
                                  "status": "confirmed", "source": "form", "history": []},
            "primaryDiagnosis.biomarkers.KRAS": {"value": "G12D", "confidence": 1.0,
                                                 "status": "confirmed", "source": "form",
                                                 "history": []},
            "primaryDiagnosis.stage": {"value": "Stage IV", "confidence": 1.0,
                                       "status": "confirmed", "source": "form", "history": []},
        }},
    }
    state.saved = []
    state.events_appended = []

    monkeypatch.setenv("FEATURE_MODELER", "true")
    monkeypatch.delenv("FEATURE_MODELER_ACTIVE", raising=False)
    monkeypatch.setattr(supabase_storage, "load_profile", lambda uid: state.profile)
    monkeypatch.setattr(supabase_storage, "load_patient_events",
                        lambda uid, limit=200, kinds=None, since=None: GOLDEN["events"])
    monkeypatch.setattr(supabase_storage, "save_connections",
                        lambda uid, c: state.saved.append(copy.deepcopy(c)) or True)
    monkeypatch.setattr(supabase_storage, "append_patient_event",
                        lambda uid, kind, path=None, payload=None, source="system",
                        session_id=None, occurred_at=None:
                        state.events_appended.append(kind) or True)
    monkeypatch.setattr(supabase_storage, "load_all_screening_history", lambda uid: {})
    monkeypatch.setattr(supabase_storage, "list_conversations",
                        lambda uid, limit=100: [])
    monkeypatch.setattr(supabase_storage, "load_all_chunks", lambda: GOLDEN["chunks"])

    import pdf_utils
    monkeypatch.setattr(pdf_utils, "hybrid_search",
                        lambda query, chunks, top_k=5, cancer_types=None: GOLDEN["chunks"])
    return state


class TestRunForUser:
    def test_success_advances_watermark_and_emits_events(self, stubbed_run, monkeypatch):
        monkeypatch.setattr(modeler, "call_modeler_llm", lambda payload: golden_output())
        result = modeler.run_for_user("user-1", trigger="test")
        assert result["status"] == "ran"
        assert result["run"]["new_edges"] == 2
        final = stubbed_run.saved[-1]
        assert final["meta"]["watermark"] == "2026-07-10T15:00:00"
        assert final["meta"]["last_run_status"] == "ok"
        assert "modeler_run" in stubbed_run.events_appended

    def test_llm_failure_holds_watermark(self, stubbed_run, monkeypatch):
        monkeypatch.setattr(modeler, "call_modeler_llm", lambda payload: None)
        result = modeler.run_for_user("user-1", trigger="test")
        assert result == {"status": "error", "reason": "llm_error"}
        final = stubbed_run.saved[-1]
        assert final["meta"]["watermark"] is None
        assert final["meta"]["last_run_status"] == "llm_error"
        assert "modeler_run" not in stubbed_run.events_appended

    def test_disabled_flag_is_hard_noop(self, stubbed_run, monkeypatch):
        monkeypatch.delenv("FEATURE_MODELER", raising=False)
        assert modeler.run_for_user("user-1") == {"status": "disabled"}
        assert stubbed_run.saved == []

    def test_debounce_skips_without_force(self, stubbed_run, monkeypatch):
        import supabase_storage
        monkeypatch.setattr(supabase_storage, "load_patient_events",
                            lambda uid, limit=200, kinds=None, since=None:
                            GOLDEN["events"][:2])   # < MIN_NEW_EVENTS
        result = modeler.run_for_user("user-1")
        assert result == {"status": "skipped", "reason": "min_events"}


# ---------------------------------------------------------------- reflections

class TestReflections:
    def test_store_reflections_dedupes(self):
        connections = fresh_connections()
        ops, _ = parse_modeler_output(golden_output(), INDEX)
        assert store_reflections(connections, ops, EVENTS, CHUNKS, NOW) == 1
        assert store_reflections(connections, ops, EVENTS, CHUNKS, NOW) == 0
        assert connections["reflections"][0]["status"] == "proposed"

    def test_enqueue_force_pends_and_respects_cap(self, monkeypatch):
        import supabase_storage
        from patient_model import ensure_beliefs
        monkeypatch.setattr(supabase_storage, "append_patient_event",
                            lambda *a, **k: True)
        monkeypatch.setattr(supabase_storage, "save_profile", lambda uid, p: True)

        profile: dict = {"patient": {}}
        ensure_beliefs(profile)
        connections = fresh_connections()
        ops, _ = parse_modeler_output(golden_output(), INDEX)
        store_reflections(connections, ops, EVENTS, CHUNKS, NOW)

        queued = modeler.enqueue_reflections("user-1", profile, connections)
        assert queued == 1
        assert connections["reflections"][0]["status"] == "queued"
        pending = profile["beliefs"]["pending"]
        assert len(pending) == 1 and pending[0]["path"] == "treatments.line"

    def test_enqueue_skips_already_known_value(self, monkeypatch):
        import supabase_storage
        from patient_model import ensure_beliefs
        monkeypatch.setattr(supabase_storage, "append_patient_event", lambda *a, **k: True)
        monkeypatch.setattr(supabase_storage, "save_profile", lambda uid, p: True)

        profile: dict = {"patient": {}}
        beliefs = ensure_beliefs(profile)
        beliefs["fields"]["treatments.line"] = {
            "value": "1st-line", "confidence": 1.0, "status": "confirmed",
            "source": "form", "history": [],
        }
        connections = fresh_connections()
        ops, _ = parse_modeler_output(golden_output(), INDEX)
        store_reflections(connections, ops, EVENTS, CHUNKS, NOW)

        queued = modeler.enqueue_reflections("user-1", profile, connections)
        assert queued == 0
        assert connections["reflections"][0]["status"] == "confirmed"
        assert profile["beliefs"]["pending"] == []
