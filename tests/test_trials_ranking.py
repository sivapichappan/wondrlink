"""
Graph-aware trial ranking unit tests (Push 3 — pure, no network).

Locks the two core guarantees:
  1. connections=None / empty graph -> byte-identical legacy scoring
  2. graph signals adjust RANKING with plain-language rationale, never exclude

Run: python3 -m pytest tests/test_trials_ranking.py -v
"""

import copy
import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "lib"))

from clinical_trials import (  # noqa: E402
    GRAPH_DEMOTION_FLOOR,
    graph_trial_signals,
    score_trial_relevance,
    validate_trial_feedback,
)

with open(os.path.join(REPO_ROOT, "tests", "fixtures", "trials_golden.json")) as f:
    GOLDEN = json.load(f)

CTX = GOLDEN["patient_context"]
GRAPH = GOLDEN["connections"]
TRIALS = {t["nct_id"]: t for t in GOLDEN["trials"]}
EXPECTED = GOLDEN["expected"]


def score_all(connections=None):
    return {nct: score_trial_relevance(copy.deepcopy(t), CTX, connections=connections)
            for nct, t in TRIALS.items()}


# ------------------------------------------------------------- regression lock

class TestLegacyRegression:
    def test_expected_legacy_scores(self):
        results = score_all(connections=None)
        for nct, expected_score in EXPECTED["legacy_scores"].items():
            assert results[nct]["score"] == expected_score, nct

    def test_none_and_empty_graph_are_byte_identical(self):
        a = score_all(connections=None)
        b = score_all(connections={})
        c = score_all(connections={"edges": []})
        assert a == b == c

    def test_legacy_ordering(self):
        results = score_all(connections=None)
        order = sorted(results, key=lambda n: results[n]["score"], reverse=True)
        assert order == EXPECTED["legacy_order"]


# ------------------------------------------------------------- graph signals

class TestGraphSignals:
    def test_contraindication_demotes_and_flips_ordering(self):
        results = score_all(connections=GRAPH)
        for nct, expected_score in EXPECTED["graph_scores"].items():
            assert results[nct]["score"] == expected_score, nct
        order = sorted(results, key=lambda n: results[n]["score"], reverse=True)
        assert order == EXPECTED["graph_order"]
        assert results["NCT01000001"]["graph"]["delta"] == -20

    def test_supports_therapy_boost_with_reason(self):
        result = score_all(connections=GRAPH)["NCT01000002"]
        assert result["graph"]["delta"] == 6
        assert any("KRAS-targeted therapy" in r for r in result["reasons"])

    def test_toxicity_history_warns_without_score_change(self):
        legacy = score_all(connections=None)["NCT01000004"]
        graph = score_all(connections=GRAPH)["NCT01000004"]
        assert graph["score"] == legacy["score"]          # delta 0
        joined = " ".join(graph["warnings"])
        for sub in EXPECTED["toxicity_warning_substrings"]:
            assert sub in joined

    def test_refuted_edges_ignored(self):
        # e4 (refuted platinum contraindication) matches trial 4's oxaliplatin;
        # if it were applied, the score would drop. It must not.
        graph = score_all(connections=GRAPH)["NCT01000004"]
        assert graph["score"] == EXPECTED["graph_scores"]["NCT01000004"]
        assert "platinum" not in " ".join(graph["warnings"]).lower()

    def test_untouched_trial_is_byte_identical(self):
        legacy = score_all(connections=None)["NCT01000003"]
        graph = score_all(connections=GRAPH)["NCT01000003"]
        assert legacy == graph and "graph" not in graph

    def test_bidirectional_synonym_matching(self):
        # Edge says the CLASS ("anti-EGFR antibodies"); trial names the DRUG.
        signals = graph_trial_signals(GRAPH, ["Cetuximab"], "a study of cetuximab")
        assert signals["delta"] == -20
        # And the reverse: edge names a drug; trial text names the class.
        drug_edge = {"edges": [{
            "id": "e", "rel": "contraindicates", "status": "corroborated",
            "strength": 1.0,
            "src": {"type": "biomarker", "key": "k", "label": "KRAS G12D"},
            "dst": {"type": "therapy_option", "key": "cetuximab", "label": "cetuximab"},
        }]}
        signals2 = graph_trial_signals(drug_edge, ["Investigational Agent"],
                                       "an anti egfr rechallenge study")
        assert signals2["delta"] == -25

    def test_demotion_stacking_cap(self):
        edges = {"edges": [
            {"id": f"e{i}", "rel": "contraindicates", "status": "corroborated",
             "strength": 1.0,
             "src": {"type": "biomarker", "key": "k", "label": "Marker"},
             "dst": {"type": "therapy_option", "key": key, "label": key}}
            for i, key in enumerate(["cetuximab", "bevacizumab", "olaparib"])
        ]}
        signals = graph_trial_signals(
            edges, ["Cetuximab", "Bevacizumab", "Olaparib"], "combination study")
        assert signals["delta"] == GRAPH_DEMOTION_FLOOR   # -75 floored at -30

    def test_warning_text_hygiene(self):
        results = score_all(connections=GRAPH)
        for result in results.values():
            for warning in result["warnings"]:
                assert "contraindicat" not in warning.lower()
                assert "; patient is" not in warning
        contra = " ".join(results["NCT01000001"]["warnings"])
        for sub in EXPECTED["contra_warning_substrings"]:
            assert sub in contra
        # Graph warning must be FIRST (mobile renders warnings[0] only).
        assert "Cetuximab" in results["NCT01000001"]["warnings"][0]

    def test_short_term_never_matches(self):
        # A 3-char edge label must not produce trial_text false positives.
        edges = {"edges": [{
            "id": "e", "rel": "contraindicates", "status": "corroborated",
            "strength": 1.0,
            "src": {"type": "biomarker", "key": "k", "label": "X"},
            "dst": {"type": "therapy_option", "key": "ici", "label": "ICI"},
        }]}
        signals = graph_trial_signals(edges, ["Pembrolizumab"],
                                      "a musician study of icicle formation")
        assert signals["delta"] == 0 and signals["edge_ids"] == []


# ------------------------------------------------------------- quick win + misc

class TestCompletedRegimen:
    def test_completed_regimen_warns_without_score_change(self):
        with_completed = score_all(connections=None)["NCT01000004"]
        bare_ctx = dict(CTX, completed_regimens=[])
        without = score_trial_relevance(copy.deepcopy(TRIALS["NCT01000004"]),
                                        bare_ctx, connections=None)
        assert with_completed["score"] == without["score"]
        joined = " ".join(with_completed["warnings"])
        for sub in EXPECTED["completed_warning_substrings"]:
            assert sub in joined


class TestFeedbackValidation:
    def test_valid(self):
        out = validate_trial_feedback({"nct_id": "nct01000001", "action": "SAVED",
                                       "surface": "tools"})
        assert out == {"nct_id": "NCT01000001", "action": "saved", "surface": "tools"}

    @pytest.mark.parametrize("body", [
        None, "x", {}, {"nct_id": "NCT123", "action": "saved"},
        {"nct_id": "NCT01000001", "action": "bogus"},
        {"nct_id": "NCT01000001; DROP TABLE", "action": "saved"},
    ])
    def test_invalid(self, body):
        assert validate_trial_feedback(body) is None
