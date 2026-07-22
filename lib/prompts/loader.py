"""
Prompt-file loader (supervisor gateway mandate: "Prompts are versioned
files in the repo, not strings scattered through code").

One file per task under lib/prompts/files/. `load_prompt(name)` returns the
file's contents EXACTLY as written (no stripping — the relocation from
inline constants is byte-for-byte, enforced by
tests/test_prompt_relocation.py SHA-256 pins). Template variables keep
their original interpolation style at the call site (.format slots,
str.replace markers), so this loader stays interpolation-agnostic.
"""

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_FILES_DIR = Path(__file__).resolve().parent / "files"

# Emergency stub if a prompt file is missing from a deployment bundle
# (e.g. an ignore-rule regression — .vercelignore's blanket *.md exclusion
# silently dropped runtime markdown once). Several prompts load at module
# import, so raising here would take the WHOLE API down; a degraded prompt
# with a CRITICAL log line and the /api/health prompt_files counter is the
# survivable failure. The stub asks the model to defer rather than guess.
_MISSING_STUB = (
    "You are a careful assistant for cancer patients. The detailed task "
    "instructions failed to load, so keep the response short, general, and "
    "safe, and recommend the person confirm anything medical with their "
    "care team."
)


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Contents of lib/prompts/files/<name>.md, exactly as stored."""
    try:
        return (_FILES_DIR / f"{name}.md").read_text()
    except OSError:
        logger.critical(f"PROMPT FILE MISSING: {name}.md — serving degraded stub")
        return _MISSING_STUB
