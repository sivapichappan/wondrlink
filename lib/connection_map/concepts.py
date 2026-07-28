"""Connection-map controlled vocabularies + concept-seed validation.

This module is the single Python source of truth for every closed enum in the
connection-map schema (SPEC-connection-map.md §4). The migration SQL mirrors
these lists in CHECK constraints, and tests/test_connection_map_migrations.py
cross-checks the two — change a value here and the matching migration must
change in the same commit (as a NEW migration; published ones are history).

No patient data flows through this module. It reads reviewable config only
(config/connection_map/*.yaml), following the safety-rules precedent of
clinical vocabulary as data.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

# --- Closed enums (spec §4; SQL CHECK constraints mirror these exactly) ---

CONCEPT_DOMAINS = (
    "biomarker",
    "treatment",
    "procedure",
    "symptom",
    "lab_or_measure",
    "daily_life",
)

CONCEPT_INSTRUMENTS = (
    "lab",
    "ehr_field",
    "report_scan",
    "pro_instrument",
    "self_report_chat",
)

RELATIONSHIP_TYPES = (
    "side_effect_of",
    "co_occurs_with",
    "indicated_by",
    "monitored_with",
    "mitigated_by",
    "acts_through",
)

EDGE_URGENCIES = ("routine", "urgent")

# Spec §4.4 defines tiers A|B|C but tier C is "discarded, never queued" —
# nothing may legitimately persist a C, so the stored enum is A|B only
# (approved deviation, PLAN.md open decision #2).
EDGE_TIERS = ("A", "B")

EDGE_STATUSES = ("candidate", "in_review", "approved", "rejected")

CANDIDATE_ORIGINS = ("literature_scan", "patient_observation")

REJECTION_REASONS = (
    "quote_does_not_support",
    "quote_out_of_context",
    "too_general",
    "wrong_relationship_type",
    "not_appropriate_for_patients",
    "clinically_incorrect",
    "duplicate",
    "chain_does_not_hold",
)

SOURCE_SCOPES = ("cancer_specific", "general_survivorship")

MAP_VERSION_STATUSES = ("draft", "published", "superseded")

PATIENT_EDGE_STATUSES = (
    "instantiated",
    "proposed",
    "confirmed",
    "refuted",
    "retired",
)

# --- Concept-seed validation ---

_SLUG_RE = re.compile(r"^[a-z0-9_]+$")

_REQUIRED_KEYS = {"slug", "domain", "display_clinical", "cancer_scopes"}
_ALLOWED_KEYS = _REQUIRED_KEYS | {
    "display_patient",
    "terminology_system",
    "terminology_code",
    "instrument",
    "notes",
    "spec_addition",
}

CONCEPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "connection_map"


def load_concepts(path: Path) -> Dict[str, Any]:
    """Load a concept-seed YAML file ({version, cancer, concepts: [...]})."""
    with open(path, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise ValueError("concept seed must be a YAML mapping")
    return doc


def validate_concepts(doc: Dict[str, Any]) -> List[str]:
    """Validate a concept-seed document. Returns a list of error strings
    (empty = valid). Never raises on bad content — the seeder aborts on any
    non-empty return and touches nothing."""
    errors: List[str] = []

    cancer = doc.get("cancer")
    if not isinstance(cancer, str) or not cancer:
        errors.append("top-level 'cancer' must be a non-empty string")
        cancer = None

    concepts = doc.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        errors.append("top-level 'concepts' must be a non-empty list")
        return errors

    seen_slugs: set = set()
    for i, c in enumerate(concepts):
        where = f"concepts[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{where}: not a mapping")
            continue

        slug = c.get("slug")
        if not isinstance(slug, str) or not _SLUG_RE.match(slug or ""):
            errors.append(f"{where}: slug {slug!r} must match ^[a-z0-9_]+$")
        elif slug in seen_slugs:
            errors.append(f"{where}: duplicate slug {slug!r}")
        else:
            seen_slugs.add(slug)
        label = slug if isinstance(slug, str) else where

        missing = _REQUIRED_KEYS - set(c.keys())
        if missing:
            errors.append(f"{label}: missing required keys {sorted(missing)}")
        unknown = set(c.keys()) - _ALLOWED_KEYS
        if unknown:
            errors.append(f"{label}: unknown keys {sorted(unknown)}")

        if c.get("domain") not in CONCEPT_DOMAINS:
            errors.append(f"{label}: domain {c.get('domain')!r} not in {CONCEPT_DOMAINS}")

        display = c.get("display_clinical")
        if not isinstance(display, str) or not display.strip():
            errors.append(f"{label}: display_clinical must be a non-empty string")

        instrument = c.get("instrument")
        if instrument is not None and instrument not in CONCEPT_INSTRUMENTS:
            errors.append(f"{label}: instrument {instrument!r} not in {CONCEPT_INSTRUMENTS}")

        scopes = c.get("cancer_scopes")
        if not isinstance(scopes, list) or not scopes or not all(
            isinstance(s, str) and s for s in scopes
        ):
            errors.append(f"{label}: cancer_scopes must be a non-empty list of strings")
        elif cancer and cancer not in scopes:
            errors.append(f"{label}: cancer_scopes must include {cancer!r}")

        if "spec_addition" in c and c["spec_addition"] is not True:
            errors.append(f"{label}: spec_addition, when present, must be true")

    return errors
