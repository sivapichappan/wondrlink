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


def derive_clinical_payload(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Pack a raw_profile into the per-cancer `clinical` JSONB payload.

    Today this is colon-shaped (primary_site, histology, biomarkers,
    treatments, surgical_history, has_ostomy/ostomy_type). When other
    cancers go ready: true, this function should consult the slug to
    pack appropriately — for Phase 1 the only ready cancer is colorectal
    and the existing raw_profile shape maps cleanly.
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
    if diagnosis.get("biomarkers"):
        payload["biomarkers"] = diagnosis["biomarkers"]
    if profile.get("treatments"):
        payload["treatments"] = profile["treatments"]
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
