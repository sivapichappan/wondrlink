"""
Per-cancer clinical payload validator.

Validates `patient_profiles.clinical` JSONB against the JSON Schema in
`config/cancers/<slug>/clinical.schema.json`. Called from save_profile
before write so invalid payloads never land in the database.

Also exposes helpers that derive the universal core fields
(cancer_slug, role, stage_group, treatment_intent) from a legacy
raw_profile blob during the dual-write window.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, ValidationError

from lib import cancer_registry as registry

logger = logging.getLogger(__name__)


_VALID_STAGES = {"0", "I", "II", "III", "IV"}
_ROMAN_NORMALIZE = {
    "1": "I", "2": "II", "3": "III", "4": "IV", "0": "0",
    "i": "I", "ii": "II", "iii": "III", "iv": "IV",
}


def normalize_stage(raw: Optional[str]) -> str:
    """Normalize a free-text stage to one of the 0/I/II/III/IV/unknown enum."""
    if not raw:
        return "unknown"
    s = str(raw).strip().upper()
    # Strip leading "STAGE " or any non-roman/non-digit suffix
    s = re.sub(r"^STAGE\s+", "", s)
    # First, exact match against the enum
    if s in _VALID_STAGES:
        return s
    # Try first token (e.g. "IIIB" -> "III", "IV-M1" -> "IV")
    head_match = re.match(r"^(0|IV|III|II|I)", s)
    if head_match:
        return head_match.group(1)
    # Numeric (1/2/3/4)
    num_match = re.match(r"^(\d)", s)
    if num_match and num_match.group(1) in _ROMAN_NORMALIZE:
        return _ROMAN_NORMALIZE[num_match.group(1)]
    return "unknown"


def derive_treatment_intent(profile: Dict[str, Any], stage_group: str) -> str:
    """Heuristic: stage IV → palliative; stage 0–III → curative; else unknown.

    Refined by treatment status: if any active treatment is flagged
    palliative/maintenance, that wins.
    """
    treatments = profile.get("treatments") or []
    if isinstance(treatments, list):
        for t in treatments:
            if not isinstance(t, dict):
                continue
            intent_field = (t.get("intent") or "").lower()
            if intent_field in ("palliative", "curative"):
                return intent_field
            line = (t.get("line") or "").lower()
            if "palliative" in line or "maintenance" in line:
                return "palliative"
    if stage_group == "IV":
        return "palliative"
    if stage_group in {"0", "I", "II", "III"}:
        return "curative"
    return "unknown"


def derive_universal_core(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the v2 universal-core columns from a legacy raw_profile blob.

    Returns a dict with cancer_slug, role, stage_group, treatment_intent.
    Used by scripts/migrate_profiles_v2.py AND by save_profile during the
    dual-write window when callers haven't yet started passing these
    fields explicitly.
    """
    diagnosis = profile.get("primaryDiagnosis") or {}
    raw_site = diagnosis.get("site") or profile.get("cancer_type") or ""
    raw_stage = diagnosis.get("stage") or profile.get("cancer_stage") or ""
    role = "caregiver" if profile.get("role") == "caregiver" else "patient"

    cancer_slug = registry.resolve_slug(raw_site)
    stage_group = normalize_stage(raw_stage)
    intent = derive_treatment_intent(profile, stage_group)

    return {
        "cancer_slug": cancer_slug,
        "role": role,
        "stage_group": stage_group,
        "treatment_intent": intent,
    }


# Canonical-form maps for legacy values. The clinical.schema.json enums
# accept the canonical form; these maps normalize common legacy phrasing
# (lowercase MSI-H, "1st line", "dmmr", "mutant", "not tested") so the
# dry-run validation passes for existing colorectal profiles.

_LINE_NORMALIZE = {
    "1st line": "first-line", "1st-line": "first-line", "1l": "first-line",
    "2nd line": "second-line", "2nd-line": "second-line", "2l": "second-line",
    "3rd line": "third-line", "3rd-line": "third-line", "3l": "third-line",
    "4th line": "third-line",
}

_MSI_NORMALIZE = {
    "msi-h": "MSI-H", "msi h": "MSI-H", "msih": "MSI-H", "high": "MSI-H",
    "msi-l": "MSI-L", "msi l": "MSI-L", "msil": "MSI-L", "low": "MSI-L",
    "mss": "MSS", "stable": "MSS",
    "not tested": "unknown", "pending": "unknown", "none": "unknown",
    "unspecified": "unknown",
}

_MMR_NORMALIZE = {
    "dmmr": "deficient", "d-mmr": "deficient", "mmr-d": "deficient",
    "pmmr": "proficient", "p-mmr": "proficient", "mmr-p": "proficient",
    "not tested": "unknown", "pending": "unknown",
    "unspecified": "unknown", "none": "unknown",
}

_GENERIC_MUTATION_NORMALIZE = {
    "mutant": "mutated", "mut": "mutated", "mutation": "mutated",
    "wt": "wild-type", "wild type": "wild-type", "wildtype": "wild-type",
    "not tested": "unknown", "pending": "unknown", "n/a": "unknown",
    "unspecified": "unknown", "none": "unknown", "": "unknown",
}

_HER2_NORMALIZE = {
    "pos": "positive", "+": "positive", "3+": "positive", "positive": "positive",
    "neg": "negative", "-": "negative", "0": "negative", "1+": "negative",
    "negative": "negative",
    "2+ amplified": "positive", "2+ non-amplified": "low", "low": "low",
    "not tested": "unknown", "pending": "unknown", "unspecified": "unknown",
}

_NTRK_NORMALIZE = {
    "positive": "fusion", "fusion+": "fusion", "fusion-positive": "fusion",
    "fusion": "fusion",
    "negative": "no-fusion", "no fusion": "no-fusion",
    "fusion-negative": "no-fusion", "no-fusion": "no-fusion",
    "not tested": "unknown", "pending": "unknown",
    "unspecified": "unknown", "": "unknown",
}

# Specific-allele tokens for genes that accept a state OR an allele name.
_BRAF_STATES = {"v600e", "non-v600e", "wild-type", "mutated", "unknown"}
_KRAS_STATES = {"wild-type", "mutated", "g12c", "g12d", "g12v", "g13d", "unknown"}


def _normalize_biomarker(key: str, value: Any) -> Any:
    """Map legacy free-text biomarker values to the schema's canonical enum."""
    if not isinstance(value, str):
        return value
    v = value.strip().lower()
    if not v:
        return "unknown"
    if key == "MSI":
        return _MSI_NORMALIZE.get(v, value)
    if key == "MMR":
        return _MMR_NORMALIZE.get(v, value)
    if key == "HER2":
        return _HER2_NORMALIZE.get(v, value)
    if key == "NTRK":
        return _NTRK_NORMALIZE.get(v, value)
    if key == "BRAF":
        if v == "v600e":
            return "V600E"
        if v == "non-v600e":
            return "non-V600E"
        return _GENERIC_MUTATION_NORMALIZE.get(v, value)
    if key == "KRAS":
        if v in ("g12c", "g12d", "g12v", "g13d"):
            return v.upper()
        return _GENERIC_MUTATION_NORMALIZE.get(v, value)
    if key in ("NRAS", "PIK3CA"):
        return _GENERIC_MUTATION_NORMALIZE.get(v, value)
    return value


def _normalize_line(value: Any) -> Any:
    """Map legacy treatment-line strings like '1st line' to the canonical enum."""
    if not isinstance(value, str):
        return value
    return _LINE_NORMALIZE.get(value.strip().lower(), value)


def derive_clinical_payload(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Pack a raw_profile into the per-cancer `clinical` JSONB payload.

    Today this is colon-shaped (primary_site, histology, biomarkers,
    treatments, surgical_history, has_ostomy/ostomy_type). When other
    cancers go ready: true, this function should consult the slug to
    pack appropriately — for Phase 1 the only ready cancer is colorectal
    and the existing raw_profile shape maps cleanly.

    Legacy free-text values (lowercase msi-h, "1st line", "mutant",
    "dmmr", "not tested") are normalized to the canonical enum form so
    the per-cancer JSON Schema validates without rejecting the row.
    """
    diagnosis = profile.get("primaryDiagnosis") or {}
    payload: Dict[str, Any] = {}

    if diagnosis.get("site"):
        site_lower = diagnosis["site"].lower()
        if "rectum" in site_lower or "rectal" in site_lower:
            payload["primary_site"] = "rectum"
        elif "colon" in site_lower:
            payload["primary_site"] = "colon"
        elif "rectosigmoid" in site_lower:
            payload["primary_site"] = "rectosigmoid"
        elif "appendix" in site_lower:
            payload["primary_site"] = "appendix"
        else:
            payload["primary_site"] = "other"

    if diagnosis.get("histology"):
        payload["histology"] = diagnosis["histology"]
    if diagnosis.get("stage"):
        payload["stage_detail"] = diagnosis["stage"]
    if diagnosis.get("dateOfDiagnosis"):
        payload["diagnosis_date"] = diagnosis["dateOfDiagnosis"]
    if diagnosis.get("biomarkers") and isinstance(diagnosis["biomarkers"], dict):
        payload["biomarkers"] = {
            k: _normalize_biomarker(k, v) for k, v in diagnosis["biomarkers"].items()
        }
    if profile.get("treatments") and isinstance(profile["treatments"], list):
        normalized_tx = []
        for t in profile["treatments"]:
            if not isinstance(t, dict):
                normalized_tx.append(t)
                continue
            t2 = dict(t)
            if "line" in t2:
                t2["line"] = _normalize_line(t2["line"])
            normalized_tx.append(t2)
        payload["treatments"] = normalized_tx
    if profile.get("surgicalHistory"):
        payload["surgical_history"] = profile["surgicalHistory"]

    # Ostomy fields are sometimes in patient, sometimes top-level
    patient = profile.get("patient") or {}
    if "ostomyType" in patient:
        payload["ostomy_type"] = patient["ostomyType"] or "unknown"
        payload["has_ostomy"] = patient["ostomyType"] not in (None, "", "none")
    elif profile.get("hasOstomy") is not None:
        payload["has_ostomy"] = bool(profile["hasOstomy"])

    return payload


def validate_clinical(cancer_slug: str, payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a clinical payload against the per-cancer JSON Schema.

    For cancers where `ready: false` or the schema file is absent, accept
    anything (returns ok=True) — the schema isn't authored yet.
    """
    schema = registry.load_clinical_schema(cancer_slug)
    if not schema:
        return True, []
    try:
        validator = Draft202012Validator(schema)
    except Exception as e:
        logger.error("Invalid clinical schema for %s: %s", cancer_slug, e)
        return True, []
    errors: List[str] = []
    for err in validator.iter_errors(payload or {}):
        path = ".".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{path}: {err.message}")
    return (len(errors) == 0), errors
