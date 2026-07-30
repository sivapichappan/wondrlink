# test_connection_map_wording.py
"""The patient-wording drafting gate (SPEC §8, §5.4).

The load-bearing assertion is that a string failing the copy rules is never
stored and never shown. A physician reviews every one of these, and the worst
outcome is not a blank field — it is a plausible-sounding sentence that breaks
§8 being put in front of her as a starting point, because a draft is an anchor
whether or not anyone intends it to be.

Offline: no model, no database.
"""

import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.review.copy_lint import lint_patient_copy  # noqa: E402

# The script is not importable as a package module; load it by path, the way
# tests/test_connection_map_migrations.py reads migration files by path.
_spec = importlib.util.spec_from_file_location(
    "draft_wording", _REPO / "scripts" / "draft_connection_map_wording.py")
draft_wording = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(draft_wording)

concept_problems = draft_wording.concept_problems
PROMPTS = _REPO / "config" / "connection_map" / "prompts"


class TestConceptNameGate:
    """A concept name is a PHRASE, and the sentence-level lint is the wrong tool
    for one: Flesch-Kincaid scored the correct answer "chemotherapy" at grade 44
    (one sentence, one word, five syllables), so running lint_patient_copy here
    rejected the good answers and passed "HER2 protein status" untouched.
    """

    def test_a_plain_name_passes(self):
        for good in ("hormone pill", "chemotherapy", "thinning bones",
                     "arm swelling or heaviness", "trouble with memory or focus"):
            assert concept_problems(good) == [], good

    def test_an_already_plain_clinical_term_is_not_rejected_for_being_unchanged(self):
        # §10.1 names most concepts plainly on purpose. Handing "joint pain"
        # back unchanged IS the right answer, and an earlier version of this
        # gate rejected 22 of 39 good names for exactly that.
        for plain in ("joint pain", "fatigue", "hot flashes", "mood", "appetite"):
            assert concept_problems(plain) == [], plain

    def test_jargon_is_refused(self):
        for jargon in ("trastuzumab", "aromatase inhibitor", "peripheral neuropathy",
                       "HER2 protein status", "LVEF decline"):
            problems = concept_problems(jargon)
            assert problems and "still clinical" in problems[0], jargon

    def test_the_readability_estimate_is_not_applied_to_a_phrase(self):
        # The regression this locks: "chemotherapy" must pass here while still
        # scoring absurdly on the sentence-level estimator.
        assert concept_problems("chemotherapy") == []
        assert lint_patient_copy("chemotherapy"), "sentence lint still rates it; that is why it is not used here"

    def test_empty_is_refused(self):
        for bad in (None, "", "   "):
            assert concept_problems(bad) == ["empty"]

    def test_an_explanation_is_refused(self):
        long = "a medicine that lowers the amount of estrogen in your body over time"
        assert any("not an explanation" in p for p in concept_problems(long))

    def test_a_sentence_is_refused(self):
        assert any("phrase, not a sentence" in p for p in concept_problems("bone density."))

    def test_the_eight_rules_still_apply(self):
        assert any("dash" in p for p in concept_problems("hormone pill — daily"))
        assert any("causal" in p for p in concept_problems("what causes aches"))
        assert any("confidence" in p for p in concept_problems("40% of people"))


class TestConnectionWordingGate:
    """Edge wording IS a sentence, so it goes through the real §8 lint — the
    same function the publication gate applies."""

    GOOD = ("Some people taking this hormone medicine notice muscle pain. "
            "Has that been true for you?")

    def test_the_house_example_passes(self):
        assert lint_patient_copy(self.GOOD) == []

    def test_a_causal_claim_is_refused(self):
        bad = "This pill causes joint pain. Has that been true for you?"
        assert lint_patient_copy(bad)

    def test_a_probability_is_refused(self):
        bad = "About 40% of people notice joint aches. Has that been true for you?"
        assert lint_patient_copy(bad)


class TestWordingPrompts:
    """Placeholders the script substitutes must exist, or the model is handed a
    literal '{evidence}' and answers about nothing."""

    RUNNER = (_REPO / "scripts" / "draft_connection_map_wording.py").read_text()

    def test_edge_prompt_placeholders_match_the_script(self):
        text = (PROMPTS / "patient_wording_edge.md").read_text()
        for placeholder in ("{src_display}", "{dst_display}", "{relationship}", "{evidence}"):
            assert placeholder in text, placeholder
            assert f'.replace("{placeholder}"' in self.RUNNER, placeholder

    def test_concept_prompt_placeholder_matches_the_script(self):
        text = (PROMPTS / "patient_wording_concept.md").read_text()
        assert "{concepts}" in text
        assert '.replace("{concepts}"' in self.RUNNER

    def test_the_prompts_do_not_themselves_break_the_rules_they_teach(self):
        # A prompt that demonstrates an em dash while forbidding em dashes is
        # teaching the model the wrong thing by example.
        for name in ("patient_wording_edge.md", "patient_wording_concept.md"):
            body = (PROMPTS / name).read_text()
            examples = [ln for ln in body.splitlines()
                        if ln.strip().startswith(">") or ln.strip().startswith("|")]
            for line in examples:
                assert "—" not in line, f"{name}: em dash in an example: {line}"


class TestScriptSafety:
    """Static guards on the drafting script itself."""

    SRC = (_REPO / "scripts" / "draft_connection_map_wording.py").read_text()

    def test_thinking_is_disabled(self):
        # Same reasoning-model trap as extraction: with thinking on, a longer
        # prompt burns the budget and json_object mode returns the cheapest
        # valid object instead of an error.
        assert '"enable_thinking": False' in self.SRC

    def test_only_candidate_edges_are_written(self):
        # patient_phrasing is hash-covered, so writing it to a signed edge would
        # void the attestation. The database refuses it too; this never asks.
        assert '.eq("status", "candidate")' in self.SRC

    def test_a_failing_draft_is_never_stored(self):
        # The update must sit AFTER the lint, on the passing branch only.
        lint_at = self.SRC.index("problems = lint_patient_copy(phrasing)")
        update_at = self.SRC.index('db.table("master_edge").update(')
        assert lint_at < update_at, "wording is stored before it is checked"

    def test_the_model_comes_from_the_registry(self):
        assert 'get_model("connection_wording")' in self.SRC
        assert "deepseek" not in self.SRC.lower(), "model ids come from model_registry only"
