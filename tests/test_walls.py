# test_walls.py
"""
The walls engine (lib/walls.py) — the only gate left after the 2026-08-24
inversion. Detection precision, the fixed template copy, the code-level
enforcement, and the voice rules every patient-facing string must obey.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from walls import (  # noqa: E402
    PROGNOSIS_DOCTOR_QUESTIONS,
    WALL_DIAGNOSIS,
    WALL_DOSING,
    WALL_LIMIT_SENTENCES,
    WALL_PROGNOSIS,
    WALL_TYPES,
    detect_wall,
    enforce_wall,
    render_prognosis_wall_response,
    wall_prompt_block,
)


def _wall(msg):
    hit = detect_wall(msg)
    return (hit["type"], hit["direct"]) if hit else None


class TestPrognosisDirect:
    """Direct personal-future asks take the canned screen-12 path."""

    def test_the_screen_12_question(self):
        assert _wall("How long do I have?") == (WALL_PROGNOSIS, True)

    def test_variants(self):
        for q in [
            "how much time do I have left",
            "Am I dying?",
            "am I going to die from this",
            "will I die?",
            "Will I survive this?",
            "will I beat this",
            "am I gonna make it",
            "What are my chances?",
            "what are my odds here",
            "what's my prognosis",
            "What is my prognosis doctor",
            "my life expectancy with this diagnosis",
            "is this going to kill me",
            "will it kill me",
            "How long do people like me usually live?",
        ]:
            assert _wall(q) == (WALL_PROGNOSIS, True), q

    def test_direct_beats_indirect_vocabulary(self):
        # Carries "survival rate" too, but the personal ask wins.
        hit = detect_wall("What are my chances? I keep reading survival rates.")
        assert hit["type"] == WALL_PROGNOSIS and hit["direct"]


class TestPrognosisIndirect:
    def test_statistics_vocabulary(self):
        for q in [
            "What is the five-year survival rate for stage 3?",
            "what's the survival rate",
            "Is this considered terminal?",
            "what is the cure rate",
            "life expectancy for someone with this",
            "chances of recurrence after surgery",
        ]:
            assert _wall(q) == (WALL_PROGNOSIS, False), q

    def test_the_word_prognosis_alone(self):
        assert _wall("What does prognosis mean?") == (WALL_PROGNOSIS, False)


class TestDiagnosis:
    def test_conclude_for_me_asks(self):
        for q in [
            "Do I have cancer?",
            "I found a lump under my arm. Is it cancer?",
            "could this be cancer",
            "can you diagnose me",
            "is my cancer back?",
            "has it spread?",
            "has my cancer spread to my liver",
            "am I in remission now?",
            "is this lump something to worry about",
            "does this mean I have a recurrence",
        ]:
            assert _wall(q) == (WALL_DIAGNOSIS, False), q


class TestDosing:
    def test_medication_change_asks(self):
        for q in [
            "Can I stop taking my pills? They make me sick.",
            "should I quit taking tamoxifen",
            "Can I skip my dose this week?",
            "should I lower my dose of the medication",
            "I missed a dose last night",
            "forgot to take my pill this morning",
            "can I take a double dose to catch up",
            "I want to wean off the meds",
            "can I pause treatment for my daughter's wedding",
            "I want to stop my chemo",
        ]:
            hit = detect_wall(q)
            assert hit and hit["type"] == WALL_DOSING, q

    def test_forgot_then_double_is_one_wall(self):
        hit = detect_wall(
            "I forgot to take my dose last night. Should I double it today?")
        assert hit["type"] == WALL_DOSING


class TestNotAWall:
    """Education and the whole of a person's life stay fully answerable."""

    def test_everyday_life_engages(self):
        for q in [
            "How do I fix my car battery?",
            "Can you give me a chocolate cake recipe?",
            "Can I still go to my granddaughter's birthday party?",
            "Recommend me a good action movie to watch tonight.",
            "I'm worried about money with all these bills",
        ]:
            assert detect_wall(q) is None, q

    def test_education_is_not_a_wall(self):
        for q in [
            "What does stage 3 mean?",
            "Why did they put me on FOLFOX?",
            "What does MSI high mean?",
            "What helps with nausea from chemo?",
            "How long does chemo usually take?",
            "What is a biopsy like?",
            "The hot flashes are really bad",
        ]:
            assert detect_wall(q) is None, q

    def test_change_verbs_without_medication_object(self):
        for q in [
            "Should I change my diet?",
            "Can I skip the gym today?",
            "should I quit my job during treatment",
        ]:
            assert detect_wall(q) is None, q

    def test_empty_and_none(self):
        assert detect_wall("") is None
        assert detect_wall(None) is None


class TestEnforceWall:
    def test_appends_when_limit_missing(self):
        out, appended = enforce_wall("Nausea often eases with small meals.",
                                     WALL_DOSING)
        assert appended
        assert WALL_LIMIT_SENTENCES[WALL_DOSING] in out
        assert out.startswith("Nausea often eases")

    def test_no_append_when_model_included_the_template(self):
        answer = ("Small meals help.\n\n"
                  + WALL_LIMIT_SENTENCES[WALL_DOSING])
        out, appended = enforce_wall(answer, WALL_DOSING)
        assert not appended
        assert out == answer

    def test_marker_is_case_insensitive(self):
        answer = "I CAN'T TELL YOU TO CHANGE ANY MEDICINE, truly."
        out, appended = enforce_wall(answer, WALL_DOSING)
        assert not appended

    def test_idempotent(self):
        once, _ = enforce_wall("Short answer.", WALL_PROGNOSIS)
        twice, appended = enforce_wall(once, WALL_PROGNOSIS)
        assert not appended
        assert twice == once

    def test_empty_answer_passes_through(self):
        assert enforce_wall("", WALL_DOSING) == ("", False)

    def test_unknown_wall_passes_through(self):
        assert enforce_wall("hi", "not-a-wall") == ("hi", False)


class TestTemplateCopy:
    """Every string here is patient-facing and skips no voice rule."""

    def _all_copy(self):
        yield render_prognosis_wall_response()
        for wall_type in WALL_TYPES:
            yield WALL_LIMIT_SENTENCES[wall_type]
            yield wall_prompt_block(wall_type)

    def test_no_em_or_en_dashes(self):
        for text in self._all_copy():
            assert "—" not in text and "–" not in text, text[:60]

    def test_no_forbidden_directive_phrases(self):
        forbidden = ["you should", "you must", "you need to", "you have to",
                     "you ought to", "tell your doctor"]
        for text in self._all_copy():
            low = text.lower()
            for phrase in forbidden:
                assert phrase not in low, f"{phrase!r} in {text[:60]!r}"

    def test_canned_prognosis_contains_the_three_questions(self):
        answer = render_prognosis_wall_response()
        assert len(PROGNOSIS_DOCTOR_QUESTIONS) == 3
        for q in PROGNOSIS_DOCTOR_QUESTIONS:
            assert q in answer

    def test_prompt_block_carries_the_verbatim_limit(self):
        for wall_type in WALL_TYPES:
            assert WALL_LIMIT_SENTENCES[wall_type] in wall_prompt_block(wall_type)

    def test_markers_stay_inside_their_sentences(self):
        # enforce_wall's detection depends on these cores staying put.
        assert "predict what will happen" in WALL_LIMIT_SENTENCES[WALL_PROGNOSIS]
        assert "tell you what this is" in WALL_LIMIT_SENTENCES[WALL_DIAGNOSIS]
        assert "change any medicine" in WALL_LIMIT_SENTENCES[WALL_DOSING]

    def test_every_wall_routes_to_the_care_team(self):
        for wall_type in WALL_TYPES:
            low = WALL_LIMIT_SENTENCES[wall_type].lower()
            assert "care team" in low or "oncologist" in low


class TestReviewRegressions:
    """Every case the 2026-08-24 adversarial review confirmed, pinned.

    The critical one first: 'how long do I have to X' logistics questions
    were getting the canned death card.
    """

    def test_logistics_how_long_is_never_the_death_card(self):
        for q in [
            "How long do I have to wait for the biopsy results?",
            "How long do I have to take letrozole?",
            "how long do I have to decide about surgery",
            "How long do I have between infusions?",
        ]:
            assert detect_wall(q) is None, q

    def test_naked_how_long_still_hits(self):
        for q in [
            "How long do I have?",
            "how long do I have left",
            "How much time do I have to live?",
            "How much longer do I have?",
            "how long until I die",
        ]:
            assert _wall(q) == (WALL_PROGNOSIS, True), q

    def test_capability_questions_are_not_prognosis(self):
        for q in [
            "Will I be okay to drive after chemo?",
            "Will I make it to my appointment on Thursday?",
            "am I going to make it to the wedding in June",
        ]:
            hit = detect_wall(q)
            assert not (hit and hit["direct"]), q

    def test_chances_of_nonsurvival_things_are_not_prognosis(self):
        for q in [
            "What are my chances of getting into the trial?",
            "what are my chances of losing my hair",
        ]:
            assert detect_wall(q) is None, q

    def test_naked_chances_still_hits(self):
        assert _wall("What are my chances?") == (WALL_PROGNOSIS, True)
        assert _wall("what are my odds here") == (WALL_PROGNOSIS, True)

    def test_cancer_as_subject_noun_is_education(self):
        for q in [
            "Is this cancer hereditary?",
            "Is this cancer treatable in most people?",
            "is that cancer common in younger women",
        ]:
            assert detect_wall(q) is None, q

    def test_site_named_diagnosis_asks_hit_the_wall(self):
        for q in [
            "Do I have lymphoma?",
            "do I have breast cancer",
            "Do I have melanoma or is it just a mole?",
        ]:
            assert _wall(q) == (WALL_DIAGNOSIS, False), q

    def test_radiation_and_immunotherapy_are_dosing_objects(self):
        for q in [
            "can I skip my radiation today",
            "should I pause immunotherapy for the trip",
            "I want to stop the radiation",
        ]:
            hit = detect_wall(q)
            assert hit and hit["type"] == WALL_DOSING, q

    def test_ios_curly_apostrophe_matches(self):
        assert _wall("What’s my prognosis?") == (WALL_PROGNOSIS, True)

    def test_trial_spot_and_options_phrasings_are_not_diagnosis(self):
        for q in [
            "is my spot in the trial confirmed?",
            "what do I have for options here",
            "Can you help me diagnose the problem with my insurance claim?",
        ]:
            hit = detect_wall(q)
            assert not (hit and hit["type"] == WALL_DIAGNOSIS), q

    def test_weaning_a_baby_is_not_a_dosing_wall(self):
        assert detect_wall("any tips for weaning my baby off breastfeeding") is None

    def test_windows_do_not_cross_line_breaks(self):
        # 'lower' and an unrelated 'dose' on the next line must not chain.
        q = "should I lower the head of my bed\nthe nurse mentioned my dose schedule"
        hit = detect_wall(q)
        assert not (hit and hit["matched"] == "change_my_medication"), hit

    def test_dosing_route_does_not_rank_itself(self):
        # The limit block must never read as softening a same-day or 911
        # escalation that the same answer carries.
        assert "safest next step" not in WALL_LIMIT_SENTENCES[WALL_DOSING]
