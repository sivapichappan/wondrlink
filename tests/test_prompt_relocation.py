# test_prompt_relocation.py
"""
SHA-256 pins for the prompts-as-files relocation (gateway mandate).

Each hash was recorded from the inline constant's exact runtime bytes
BEFORE the move; the loaded file must match forever. A deliberate prompt
change must update its pin IN ITS OWN EVAL WINDOW (never alongside a model
swap) — this test is what makes an accidental drive-by prompt edit loud.
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from prompts.loader import load_prompt  # noqa: E402

PINS = {
    # ALL re-pinned 2026-08-03: every em dash removed from every prompt file.
    # The style rule ("no em dashes") had been in chat_base since the start and
    # was broken constantly, which is not really the model's fault -- it was
    # being told not to use a mark its own instructions used 29 times, with
    # another 10-46 in each per-cancer overlay. A model copies the register of
    # its instructions more reliably than it obeys a rule stated inside them.
    # Punctuation only; no instruction was added, removed or reworded. Shipped
    # in its own commit, separate from the output-side enforcement, so the two
    # do not share an eval window.
    # chat_base re-pinned 2026-07-25: the literal product name became the
    # {app_name} slot (branding constant). The ASSEMBLED prompt was proven
    # byte-identical to the pre-change fingerprints across all 10 cancers,
    # so this is not a prompt-text change for eval purposes.
    "chat_base": "b48157f057b0a1a032ee89b69c1fd04c194d3cbbcdd1c2c07c2afe3cfe20eecc",
    "extractor": "75071c93cc9959e2fcc51f67299fbef2c29b50ee6739472b541d2603606fd394",
    "verifier": "16a6157963ca972f9190fb3d7833bd3376620b5eb2f8b58011f933fef419ad33",
    "subquery": "fcd46285f624d09b77867a8eaa229b506a48f744df75b8272da6cd6d3f363129",
    "previsit": "4732f5400e4c4d23f001890a7a12b84c23d98a8bbdf2a0659c56916509a99217",
    "visit_recap": "3600aa331a7b77d43869da9cdb57ac4e397f9f92430614db71b687a9af9e2bec",
    "insurance_appeal": "ca7fc0e8586422fb931280f8ddd6ed13ea288d17d8c91af9449c0e436710595a",
    "deep_research": "adeaa3133022ba6eefc0b0316edf251498dc4dc14831d3a0d6ca5145be94e2e1",
    "modeler": "b27fc61fe5762472aad9c6c679f495574c730d4c29095c6200b6c86b0f14cdfc",
}


def test_all_relocated_prompts_are_byte_identical():
    mismatches = []
    for name, want in PINS.items():
        got = hashlib.sha256(load_prompt(name).encode()).hexdigest()
        if got != want:
            mismatches.append(name)
    assert not mismatches, (
        f"Prompt file(s) changed: {mismatches}. If deliberate, bump the pin "
        "in its own eval window; if not, revert the file."
    )


def test_classify_prompt_exists_and_has_markers():
    # classify.md predates this relocation and changes with the safety
    # rules — not pinned, but its template markers must survive edits.
    text = load_prompt("classify")
    for marker in ("<<APP_NAME>>", "<<RULES_JSON>>", "<<EMERGENCY_NUMBER>>",
                   "<<ON_ACTIVE_TREATMENT>>", "<<PERSPECTIVE>>"):
        assert marker in text, f"classify.md lost marker {marker}"
