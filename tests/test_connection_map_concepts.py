# test_connection_map_concepts.py
"""Guardrails for the connection-map concept vocabulary (SPEC §4.1, §10.1).

The seed YAML is the input to pass 1: an extractor may only emit concepts that
exist here, so a missing or misspelled slug silently removes an extraction
target. These tests pin the §10.1 list verbatim and pin the additions to
exactly the 7 the spec's own extraction targets require.
"""

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.concepts import (  # noqa: E402
    CONCEPT_DOMAINS,
    CONCEPT_INSTRUMENTS,
    EDGE_TIERS,
    concept_rows,
    load_concepts,
    validate_concepts,
)

SEED_PATH = _REPO / "config" / "connection_map" / "concepts_breast.yaml"

# Spec §10.1, transcribed. Slugs are ours; the display strings they carry are
# the spec's wording, asserted below.
SPEC_10_1 = {
    "biomarker": ["er_status", "pr_status", "her2_status", "ki67", "menopausal_status"],
    "treatment": [
        "aromatase_inhibitor", "tamoxifen", "ovarian_suppression",
        "anthracycline_chemotherapy", "taxane_chemotherapy", "trastuzumab",
        "radiation_therapy", "bisphosphonate_or_denosumab",
    ],
    "procedure": [
        "lumpectomy", "mastectomy", "sentinel_node_biopsy",
        "axillary_node_dissection", "breast_reconstruction",
    ],
    "symptom": [
        "joint_pain", "muscle_pain", "hot_flashes", "night_sweats", "fatigue",
        "peripheral_neuropathy", "balance_problems", "falls", "nausea",
        "hair_loss_or_thinning", "lymphedema", "vaginal_dryness",
        "painful_intercourse", "low_libido", "cognitive_complaints",
        "cardiac_symptoms", "fever", "vaginal_bleeding", "leg_pain_or_swelling",
        "arm_redness_or_warmth", "weight_gain", "general_pain",
    ],
    "lab_or_measure": [
        "lvef", "bone_mineral_density", "neutrophil_count", "vitamin_d", "body_weight",
    ],
    "daily_life": [
        "sleep_quality", "mood", "anxiety", "physical_activity", "appetite",
        "sexual_health", "work_status", "medication_adherence",
    ],
}

# Concepts §10.2-§10.4 reference that §10.1 omits (PLAN.md conflict #8).
EXPECTED_ADDITIONS = {
    "skin_changes", "scar_numbness", "lvef_decline", "bone_mineral_density_loss",
    "annual_gynecologic_assessment", "arm_exercise_and_skin_care", "sleep_routine",
}


@pytest.fixture(scope="module")
def doc():
    return load_concepts(SEED_PATH)


@pytest.fixture(scope="module")
def by_slug(doc):
    return {c["slug"]: c for c in doc["concepts"]}


class TestSeedFile:
    def test_validates_clean(self, doc):
        assert validate_concepts(doc) == []

    def test_cancer_is_breast(self, doc):
        assert doc["cancer"] == "breast"

    def test_every_spec_concept_present(self, by_slug):
        expected = {s for slugs in SPEC_10_1.values() for s in slugs}
        assert expected - set(by_slug) == set()

    def test_domains_match_spec(self, by_slug):
        for domain, slugs in SPEC_10_1.items():
            for slug in slugs:
                assert by_slug[slug]["domain"] == domain, slug

    def test_symptom_count_is_the_specs_twentytwo(self):
        assert len(SPEC_10_1["symptom"]) == 22

    def test_no_extra_concepts_beyond_spec_and_additions(self, by_slug):
        expected = {s for slugs in SPEC_10_1.values() for s in slugs} | EXPECTED_ADDITIONS
        assert set(by_slug) == expected

    def test_additions_are_exactly_the_expected_set(self, by_slug):
        flagged = {s for s, c in by_slug.items() if c.get("spec_addition")}
        assert flagged == EXPECTED_ADDITIONS

    def test_additions_explain_themselves(self, by_slug):
        for slug in EXPECTED_ADDITIONS:
            assert by_slug[slug].get("notes"), f"{slug} must record why it was added"

    def test_spec_concepts_are_not_flagged_as_additions(self, by_slug):
        for slugs in SPEC_10_1.values():
            for slug in slugs:
                assert "spec_addition" not in by_slug[slug], slug

    def test_display_patient_is_null_everywhere(self, by_slug):
        # §5.4: patient wording is the reviewer's job. Nothing here may ship
        # patient-facing text that no physician has approved.
        for slug, c in by_slug.items():
            assert c["display_patient"] is None, slug

    def test_spec_wording_preserved_for_parenthetical_concepts(self, by_slug):
        assert by_slug["peripheral_neuropathy"]["display_clinical"] == (
            "peripheral neuropathy (numbness or tingling in hands and feet)")
        assert by_slug["lymphedema"]["display_clinical"] == (
            "lymphedema (arm swelling or heaviness)")
        assert by_slug["cognitive_complaints"]["display_clinical"] == (
            "cognitive complaints (memory, concentration, word finding)")
        assert by_slug["cardiac_symptoms"]["display_clinical"] == (
            "cardiac symptoms (breathlessness, swelling, palpitations)")
        assert by_slug["medication_adherence"]["display_clinical"] == (
            "taking the pill as prescribed")

    def test_measure_and_finding_concepts_stay_distinct(self, by_slug):
        # §10.2 targets "LVEF decline" and "bone mineral density loss" as
        # findings; §10.1 lists LVEF and bone mineral density as measures.
        # Collapsing either pair would silently retarget an extraction row.
        assert by_slug["lvef"]["slug"] != by_slug["lvef_decline"]["slug"]
        assert by_slug["bone_mineral_density"]["slug"] != (
            by_slug["bone_mineral_density_loss"]["slug"])

    def test_instruments_valid_and_present(self, by_slug):
        for slug, c in by_slug.items():
            assert c.get("instrument") in CONCEPT_INSTRUMENTS, slug

    def test_all_scoped_to_breast(self, by_slug):
        for slug, c in by_slug.items():
            assert "breast" in c["cancer_scopes"], slug


class TestValidator:
    def _base(self):
        return {
            "version": 1,
            "cancer": "breast",
            "concepts": [{
                "slug": "fatigue", "domain": "symptom",
                "display_clinical": "fatigue", "display_patient": None,
                "instrument": "self_report_chat", "cancer_scopes": ["breast"],
            }],
        }

    def test_accepts_minimal_valid_doc(self):
        assert validate_concepts(self._base()) == []

    def test_rejects_duplicate_slug(self):
        doc = self._base()
        doc["concepts"].append(dict(doc["concepts"][0]))
        assert any("duplicate slug" in e for e in validate_concepts(doc))

    def test_rejects_bad_slug_format(self):
        doc = self._base()
        doc["concepts"][0]["slug"] = "Joint Pain"
        assert any("must match" in e for e in validate_concepts(doc))

    def test_rejects_unknown_domain(self):
        doc = self._base()
        doc["concepts"][0]["domain"] = "vibes"
        assert any("domain" in e for e in validate_concepts(doc))

    def test_rejects_unknown_instrument(self):
        doc = self._base()
        doc["concepts"][0]["instrument"] = "vibes"
        assert any("instrument" in e for e in validate_concepts(doc))

    def test_rejects_empty_display_clinical(self):
        doc = self._base()
        doc["concepts"][0]["display_clinical"] = "   "
        assert any("display_clinical" in e for e in validate_concepts(doc))

    def test_rejects_missing_required_key(self):
        doc = self._base()
        del doc["concepts"][0]["cancer_scopes"]
        assert any("missing required keys" in e for e in validate_concepts(doc))

    def test_rejects_unknown_key(self):
        doc = self._base()
        doc["concepts"][0]["confidence"] = 0.9
        assert any("unknown keys" in e for e in validate_concepts(doc))

    def test_rejects_scope_without_the_files_cancer(self):
        doc = self._base()
        doc["concepts"][0]["cancer_scopes"] = ["lung"]
        assert any("must include" in e for e in validate_concepts(doc))

    def test_rejects_empty_concept_list(self):
        doc = self._base()
        doc["concepts"] = []
        assert validate_concepts(doc) != []

    def test_rejects_falsey_spec_addition(self):
        doc = self._base()
        doc["concepts"][0]["spec_addition"] = False
        assert any("spec_addition" in e for e in validate_concepts(doc))


class TestSeedRows:
    def test_row_columns_match_the_table(self, doc):
        rows = concept_rows(doc)
        expected = {"slug", "domain", "display_clinical", "display_patient",
                    "terminology_system", "terminology_code", "instrument",
                    "cancer_scopes"}
        assert rows and all(set(r) == expected for r in rows)

    def test_authoring_metadata_stays_out_of_the_database(self, doc):
        # notes / spec_addition explain the YAML to a reader; they are not
        # columns and must not be sent as ones.
        for row in concept_rows(doc):
            assert "notes" not in row and "spec_addition" not in row

    def test_optional_columns_are_explicit_nulls(self, doc):
        # Written explicitly so a re-seed cannot leave a stale value behind.
        rows = {r["slug"]: r for r in concept_rows(doc)}
        assert rows["fatigue"]["terminology_system"] is None
        assert rows["fatigue"]["display_patient"] is None

    def test_row_count_matches_the_seed(self, doc):
        assert len(concept_rows(doc)) == len(doc["concepts"]) == 60


class TestEnums:
    def test_domains_cover_the_spec(self):
        assert set(CONCEPT_DOMAINS) == set(SPEC_10_1)

    def test_tier_c_is_not_storable(self):
        # §4.4: tier C is "discarded, never queued" (PLAN.md decision #2).
        assert "C" not in EDGE_TIERS
        assert set(EDGE_TIERS) == {"A", "B"}
