"""Prompt composition: base + per-cancer overlay.

Replaces the monolithic ENHANCED_SYSTEM_PROMPT in lib/llm_utils.py:216.

Usage:
    from lib.prompts import assemble_system_prompt
    system = assemble_system_prompt("colorectal")
"""

from .base import BASE_SYSTEM_PROMPT_TEMPLATE
from .overlay import compile_overlay, assemble_system_prompt

__all__ = [
    "BASE_SYSTEM_PROMPT_TEMPLATE",
    "compile_overlay",
    "assemble_system_prompt",
]
