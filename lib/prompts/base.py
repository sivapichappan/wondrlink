from .loader import load_prompt
"""
Base (cancer-agnostic) system prompt template.

This is everything that should be invariant across cancers: persona framing,
patient-profile usage framework, urgency calibration, safety rules, tone +
empathy, terminology guardrails, escalation, citation rules, formatting.

Per-cancer specifics — biomarker implications, common regimens, surveillance
phrasing — live in `config/cancers/<slug>/overlay.md` and are slotted in by
`assemble_system_prompt()`.

Template placeholders:
  {cancer_display_name}       e.g. "Colorectal cancer"
  {cancer_display_name_lower} e.g. "colorectal cancer"
  {cancer_overlay}            the per-cancer prompt block (or empty when overlay is missing)
"""

BASE_SYSTEM_PROMPT_TEMPLATE = load_prompt("chat_base")
