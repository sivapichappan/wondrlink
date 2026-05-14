"""
Per-cancer overlay compilation + system-prompt assembly.

`assemble_system_prompt(slug)` returns the full system prompt for a given
cancer by interpolating `BASE_SYSTEM_PROMPT_TEMPLATE` with:
  - {cancer_display_name}
  - {cancer_display_name_lower}
  - {cancer_overlay}  — the per-cancer text block (hand-written overlay.md)

When the cancer is unknown or `ready: false` with no overlay.md, a generic
stub overlay is used so the prompt still composes cleanly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from lib import cancer_registry as registry

from .base import BASE_SYSTEM_PROMPT_TEMPLATE


GENERIC_OVERLAY = (
    "## CANCER CONTEXT\n\n"
    "This cancer type is not yet fully configured. Use general oncology knowledge from the "
    "MEDICAL GUIDELINES section below. Defer specific regimen choices, biomarker interpretations, "
    "and surveillance schedules to the patient's oncology team rather than guessing."
)


@lru_cache(maxsize=32)
def compile_overlay(slug: Optional[str]) -> str:
    """Return the per-cancer overlay text. Cached per slug."""
    cfg = registry.get_or_fallback(slug)
    if not cfg or not cfg.get("ready"):
        # Try to load an overlay.md anyway (some not-yet-ready cancers may
        # have a draft overlay). Fall back to generic if missing.
        text = registry.load_overlay_md(cfg.get("slug")) if cfg else None
        return text or GENERIC_OVERLAY

    text = registry.load_overlay_md(cfg["slug"])
    return text or GENERIC_OVERLAY


@lru_cache(maxsize=32)
def assemble_system_prompt(slug: Optional[str]) -> str:
    """Compose base + overlay for the requested cancer.

    Unknown slugs fall back to the registry default (currently colorectal),
    so existing callers that pass nothing keep working unchanged.
    """
    cfg = registry.get_or_fallback(slug)
    display = cfg.get("display_name") or "Cancer"
    return BASE_SYSTEM_PROMPT_TEMPLATE.format(
        cancer_display_name=display,
        cancer_display_name_lower=display.lower(),
        cancer_overlay=compile_overlay(cfg.get("slug")),
    )
