"""
Cancer config registry.

Auto-discovers `config/cancers/<slug>/` directories at import time and exposes:
  - registry.get(slug)        → full config dict (cancer.yaml + lazy-loaded siblings)
  - registry.list_all()       → all slugs known to the system
  - registry.list_ready()     → slugs where ready: true (currently colorectal only)
  - registry.is_ready(slug)   → bool
  - registry.display_name(slug)
  - registry.exists(slug)

Used by:
  - lib/prompts/overlay.py        (system prompt overlay)
  - lib/clinical_trials.py        (condition string + biomarker scoring)
  - lib/surveillance.py           (per-cancer surveillance rubric dispatch)
  - lib/hero.py                   (phase rubric + suggestions)
  - lib/profile_validator.py      (clinical payload schema lookup)
  - api/index.py                  (signup validation + chat routing)
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jsonschema import Draft202012Validator, ValidationError

logger = logging.getLogger(__name__)

# Resolve config dir relative to repo root (lib/ is one level down).
_REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = _REPO_ROOT / "config" / "cancers"
_SCHEMA_PATH = CONFIG_DIR / "_schema" / "cancer.schema.json"

# Fallback used when a slug isn't recognized — the system continues to function
# but treats the user as "general cancer support" with the general-only corpus.
_FALLBACK_SLUG = "colorectal"  # current single ready cancer; safe default for v1


@lru_cache(maxsize=1)
def _load_schema() -> Draft202012Validator:
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Cancer schema missing: {_SCHEMA_PATH}")
    with _SCHEMA_PATH.open() as f:
        schema = json.load(f)
    return Draft202012Validator(schema)


def _read_yaml(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _discover() -> Dict[str, Dict[str, Any]]:
    """Walk config/cancers/, load + validate each cancer.yaml. Cached."""
    out: Dict[str, Dict[str, Any]] = {}
    if not CONFIG_DIR.exists():
        logger.warning("config/cancers/ does not exist; cancer registry is empty")
        return out

    validator = _load_schema()

    for child in sorted(CONFIG_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        cancer_yaml = child / "cancer.yaml"
        if not cancer_yaml.exists():
            logger.warning("Skipping %s — no cancer.yaml", child.name)
            continue
        try:
            data = _read_yaml(cancer_yaml) or {}
        except Exception as e:
            logger.error("Failed to parse %s: %s", cancer_yaml, e)
            continue

        try:
            validator.validate(data)
        except ValidationError as e:
            logger.error(
                "Invalid cancer.yaml at %s (will be ignored): %s",
                cancer_yaml,
                e.message,
            )
            continue

        slug = data.get("slug")
        if slug != child.name:
            logger.error(
                "Slug mismatch in %s: yaml slug=%r vs dir=%r — skipping",
                cancer_yaml,
                slug,
                child.name,
            )
            continue

        data["_dir"] = str(child)
        out[slug] = data

    if not out:
        logger.warning("No cancers discovered in %s", CONFIG_DIR)
    return out


# ----- public API ---------------------------------------------------------

def list_all() -> List[str]:
    return sorted(_discover().keys())


def list_ready() -> List[str]:
    return sorted(s for s, cfg in _discover().items() if cfg.get("ready"))


def exists(slug: str) -> bool:
    return bool(slug) and slug in _discover()


def is_ready(slug: str) -> bool:
    cfg = _discover().get(slug)
    return bool(cfg and cfg.get("ready"))


def get(slug: str) -> Optional[Dict[str, Any]]:
    """Return the cancer.yaml dict (with _dir injected) or None."""
    return _discover().get(slug)


def get_or_fallback(slug: Optional[str]) -> Dict[str, Any]:
    """Always returns a valid config — falls back to colorectal if slug unknown."""
    cfg = get(slug) if slug else None
    if cfg is not None:
        return cfg
    return get(_FALLBACK_SLUG) or {"slug": _FALLBACK_SLUG, "display_name": "Cancer"}


def display_name(slug: Optional[str]) -> str:
    cfg = get_or_fallback(slug)
    return cfg.get("display_name") or "Cancer"


def resolve_slug(raw: Optional[str]) -> str:
    """Normalize free-text site (e.g. "colon", "Colorectal Cancer") to a known slug.

    Accepts the slug itself, the display name, any alias, or a substring of any.
    Falls back to the registry's _FALLBACK_SLUG when nothing matches.
    """
    if not raw:
        return _FALLBACK_SLUG
    needle = raw.strip().lower()

    for slug, cfg in _discover().items():
        if needle == slug:
            return slug
        if needle == (cfg.get("display_name") or "").lower():
            return slug
        for alias in cfg.get("aliases") or []:
            if needle == alias.lower():
                return slug
        for cond in cfg.get("clinicaltrials_conditions") or []:
            if needle == cond.lower():
                return slug

    # substring pass — only against slug + display + aliases
    for slug, cfg in _discover().items():
        if slug in needle or needle in slug:
            return slug
        display = (cfg.get("display_name") or "").lower()
        if display and (display in needle or needle in display):
            return slug
        for alias in cfg.get("aliases") or []:
            a = alias.lower()
            if a in needle or needle in a:
                return slug

    return _FALLBACK_SLUG


# ----- sibling-file loaders ----------------------------------------------

def load_overlay_md(slug: str) -> Optional[str]:
    cfg = get(slug)
    if not cfg:
        return None
    p = Path(cfg["_dir"]) / "overlay.md"
    if not p.exists():
        return None
    return p.read_text()


def load_phase_rubric(slug: str) -> Optional[Dict[str, Any]]:
    cfg = get(slug)
    if not cfg:
        return None
    return _read_yaml(Path(cfg["_dir"]) / "phase_rubric.yaml")


def load_surveillance(slug: str) -> Optional[Dict[str, Any]]:
    cfg = get(slug)
    if not cfg:
        return None
    return _read_yaml(Path(cfg["_dir"]) / "surveillance.yaml")


def load_trial_synonyms(slug: str) -> Optional[Dict[str, Any]]:
    cfg = get(slug)
    if not cfg:
        return None
    direct = _read_yaml(Path(cfg["_dir"]) / "trial_synonyms.yaml")
    if direct is not None:
        return direct
    # Fall back to cancer.yaml fields
    return {
        "conditions": cfg.get("clinicaltrials_conditions") or [],
        "stage_specific": cfg.get("stage_specific_conditions") or {},
    }


def load_resources(slug: str) -> Optional[Dict[str, Any]]:
    cfg = get(slug)
    if not cfg:
        return None
    return _read_yaml(Path(cfg["_dir"]) / "resources.yaml")


def load_biomarker_implications(slug: str) -> Dict[str, Any]:
    """Returns the implications dict, or empty dict if missing (graceful)."""
    cfg = get(slug)
    if not cfg:
        return {}
    data = _read_yaml(Path(cfg["_dir"]) / "biomarker_implications.yaml")
    return (data or {}).get("implications", {}) or {}


def load_clinical_schema(slug: str) -> Optional[Dict[str, Any]]:
    cfg = get(slug)
    if not cfg:
        return None
    return _read_json(Path(cfg["_dir"]) / "clinical.schema.json")
