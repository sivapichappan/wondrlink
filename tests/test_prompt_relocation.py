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
    "chat_base": "e38b88334ee4a8788ea5935c2f304bc443acf9f2bdd3f7a2377a9d6d84a05955",
    "extractor": "0908762406493729a240c8ed052dc5dadfaf1a7d6c87fc267a72ace8a77870ec",
    "verifier": "e4b2cda11fff718ffed4f69c1bf79d6fe6a558753d100fe1db45d7978b5e7be0",
    "subquery": "d2e50e16c8893d31b864972334223fc631fe97dc51176aed4326e22a46674b38",
    "previsit": "c7970a7f8bfffeafa904492b5cc868d74159901f33f0ba0600059eb43da195e6",
    "visit_recap": "2e795e273d59a34393fe06824cdd6a5e40ca55de4bf3152ca3804cc2f3d5bb6f",
    "insurance_appeal": "26dd8111ddc125697fe1ed2d8c4f89511ba060d937511087b98e2031f1259faa",
    "deep_research": "11bfe4f59ddd248ea2a7b5a4b113152ac49412230a0e22d527b9dade504faef2",
    "modeler": "ac05cf8eb0026a0a2d8df6c1305ea4e61a79950f2dca3ef75cc4ee732befe920",
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
    for marker in ("<<RULES_JSON>>", "<<EMERGENCY_NUMBER>>",
                   "<<ON_ACTIVE_TREATMENT>>", "<<PERSPECTIVE>>"):
        assert marker in text, f"classify.md lost marker {marker}"
