# test_check_in.py
"""
Check-ins as engine-chosen questions (redesign change 4).

The six questionnaires are gone. What replaces them has to hold three
promises: at most 2-3 questions, each tied to what this person is actually
being treated with, and "Not now" that actually means it.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from check_in import (  # noqa: E402
    CHECK_IN_INTERVAL_DAYS,
    COOLDOWN_DAYS,
    MAX_QUESTIONS,
    check_in_due,
    load_bank,
    record_check_in,
    select_check_in,
)

_REPO = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 8, 25, 12, 0, 0)


def _profile(*regimens, status="active"):
    return {"treatments": [{"regimen": r, "status": status} for r in regimens]}


class TestAskBudget:
    def test_never_more_than_three(self):
        qs = select_check_in(_profile("FOLFOX", "capecitabine", "pembrolizumab"), {}, NOW)
        assert len(qs) <= MAX_QUESTIONS == 3

    def test_returns_patient_ready_shape(self):
        qs = select_check_in(_profile("FOLFOX"), {}, NOW)
        assert qs
        for q in qs:
            assert set(q) == {"id", "topic", "text", "chips"}
            assert q["text"] and isinstance(q["chips"], list)


class TestQuestionsFollowTheTreatment:
    def test_oxaliplatin_gets_the_cold_neuropathy_question(self):
        ids = [q["id"] for q in select_check_in(_profile("FOLFOX"), {}, NOW)]
        assert "neuropathy_cold" in ids

    def test_endocrine_therapy_gets_joint_aches_not_cold_tingling(self):
        ids = [q["id"] for q in select_check_in(_profile("letrozole"), {}, NOW)]
        assert "joint_aches" in ids
        assert "neuropathy_cold" not in ids

    def test_immunotherapy_gets_its_own_questions(self):
        ids = [q["id"] for q in select_check_in(_profile("pembrolizumab"), {}, NOW)]
        assert "skin_rash_io" in ids or "diarrhea_io" in ids

    def test_no_treatment_still_gets_general_questions(self):
        qs = select_check_in({}, {}, NOW)
        assert 0 < len(qs) <= MAX_QUESTIONS

    def test_completed_treatments_do_not_drive_questions(self):
        ids = [q["id"] for q in select_check_in(_profile("FOLFOX", status="completed"), {}, NOW)]
        assert "neuropathy_cold" not in ids

    def test_general_questions_do_not_pad_a_full_specific_check_in(self):
        # Two or more treatment-tied questions means no generic filler.
        qs = select_check_in(_profile("FOLFOX"), {}, NOW)
        bank = {q["id"]: q for q in load_bank()["questions"]}
        specific = [q for q in qs if "*" not in bank[q["id"]]["match"]]
        if len(specific) >= 2:
            assert len(specific) == len(qs)


class TestCooldownAndTheEscapeHatch:
    def test_an_asked_question_rests(self):
        state = {}
        first = select_check_in(_profile("FOLFOX"), state, NOW)
        record_check_in(state, [q["id"] for q in first], NOW)
        again = select_check_in(_profile("FOLFOX"), state, NOW + timedelta(days=1))
        assert not set(q["id"] for q in again) & set(q["id"] for q in first)

    def test_the_cooldown_expires(self):
        state = {}
        first = select_check_in(_profile("FOLFOX"), state, NOW)
        record_check_in(state, [q["id"] for q in first], NOW)
        later = select_check_in(_profile("FOLFOX"), state,
                                NOW + timedelta(days=COOLDOWN_DAYS + 1))
        assert set(q["id"] for q in later) & set(q["id"] for q in first)

    def test_declining_counts_as_answered(self):
        """"Not now" is a settled question, not a snooze button."""
        state = {}
        offered = select_check_in(_profile("letrozole"), state, NOW)
        record_check_in(state, [q["id"] for q in offered], NOW)  # declined
        again = select_check_in(_profile("letrozole"), state, NOW + timedelta(hours=2))
        assert not set(q["id"] for q in again) & set(q["id"] for q in offered)

    def test_the_log_stays_bounded(self):
        state = {}
        for day in range(30):
            record_check_in(state, [f"q{day}a", f"q{day}b", f"q{day}c"],
                            NOW + timedelta(days=day))
        assert len(state["check_in_log"]) <= 50


class TestWhenTheCheckInIsOffered:
    def test_due_for_a_new_patient(self):
        assert check_in_due({}, NOW) is True

    def test_not_due_right_after_one(self):
        state = {}
        record_check_in(state, ["tiredness"], NOW)
        assert check_in_due(state, NOW + timedelta(days=1)) is False

    def test_due_again_after_the_interval(self):
        state = {}
        record_check_in(state, ["tiredness"], NOW)
        assert check_in_due(state, NOW + timedelta(days=CHECK_IN_INTERVAL_DAYS + 1)) is True

    def test_a_corrupt_timestamp_does_not_block_check_ins_forever(self):
        assert check_in_due({"last_check_in_at": "not-a-date"}, NOW) is True


class TestTheCopyIsPatientFacing:
    """These strings go straight to a patient without passing enforce_voice,
    so they must be clean by construction — same rule as the wall copy."""

    BANK = json.loads((_REPO / "config" / "check_in" / "questions.json").read_text())

    def _all_copy(self):
        # EVERY patient-facing string, including the caregiver variants —
        # they reach a real person exactly like the self ones do, and an
        # unchecked variant is how a dash or a "you should" gets in.
        for q in self.BANK["questions"]:
            yield q["text"]
            yield from q.get("chips", [])
            for key in ("text_caregiver",):
                if q.get(key):
                    yield q[key]

    def test_no_dashes(self):
        for text in self._all_copy():
            assert "—" not in text and "–" not in text, text

    def test_no_forbidden_directive_phrases(self):
        forbidden = ["you should", "you must", "you need to", "you have to",
                     "you ought to", "tell your doctor"]
        for text in self._all_copy():
            low = text.lower()
            for phrase in forbidden:
                assert phrase not in low, f"{phrase!r} in {text!r}"

    def test_no_instrument_names_or_scores_reach_the_patient(self):
        """The whole point of the change: "Depression (PHQ-9)" and
        "LATEST PHQ-9: Moderately severe" are what we are replacing."""
        banned = ["phq", "gad-7", "gad7", "pss", "premm", "score", "severity",
                  "questionnaire", "scale", "ecog"]
        for text in self._all_copy():
            low = text.lower()
            for term in banned:
                assert term not in low, f"{term!r} in {text!r}"

    def test_every_question_has_chips_and_a_reason(self):
        for q in self.BANK["questions"]:
            assert q.get("chips"), q["id"]
            # `why` is for the clinician reviewing the bank, not the patient.
            assert q.get("why"), q["id"]

    def test_ids_are_unique(self):
        ids = [q["id"] for q in self.BANK["questions"]]
        assert len(ids) == len(set(ids))

    def test_the_bank_ships_no_canned_acknowledgement(self):
        """An answer is sent into the conversation like any message, so
        Sage's own reply acknowledges it. A `follow` string here would be
        reviewed as if it shipped, and never reach anyone."""
        for q in self.BANK["questions"]:
            assert "follow" not in q, q["id"]
            assert "follow_caregiver" not in q, q["id"]


class TestCaregiverPerspective:
    """A caregiver account is held by one person and is ABOUT another."""

    def test_caregiver_gets_the_written_variant(self):
        qs = select_check_in(_profile("FOLFOX"), {}, NOW, perspective="caregiver")
        texts = [q["text"] for q in qs]
        assert any("their fingers" in t for t in texts), texts
        assert not any("your" in t.lower() for t in texts), texts

    def test_self_is_unchanged_and_is_the_default(self):
        default = select_check_in(_profile("FOLFOX"), {}, NOW)
        explicit = select_check_in(_profile("FOLFOX"), {}, NOW, perspective="self")
        assert default == explicit
        assert any("your fingers" in q["text"] for q in default)

    def test_an_unknown_perspective_falls_back_to_self(self):
        qs = select_check_in(_profile("FOLFOX"), {}, NOW, perspective="nonsense")
        assert any("your fingers" in q["text"] for q in qs)

