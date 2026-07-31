# test_perspective.py
"""Caregiver perspective in patient-facing copy.

A caregiver account is held by one person and is ABOUT another. Onboarding asked
which it was and stored it, then nothing read it back, so every screen addressed
the holder as the patient: "Add my medical details" to someone managing their
mother's care, and a symptom check-in asking how "you've" felt.

Two properties matter here and they pull in opposite directions:

  1. Copy about the PATIENT must follow the perspective.
  2. Copy about the ACCOUNT must NOT. The password is the holder's, the account
     being deleted is the holder's, the privacy rights are the holder's. Making
     those say "their" would be a worse bug than the one being fixed, and a
     sweeping find-and-replace would have done exactly that.

Offline: reads source files, no app, no database.
"""

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

MOBILE = _REPO / "mobile"
HELPER = (MOBILE / "lib" / "perspective.ts").read_text()


def screen(rel: str) -> str:
    return (MOBILE / rel).read_text()


class TestTheServerSendsWhoTheAppIsAbout:
    """The app cannot get the perspective right without being told it."""

    API = (_REPO / "api" / "index.py").read_text()
    STORAGE = (_REPO / "lib" / "supabase_storage.py").read_text()
    TYPES = (_REPO / "shared" / "types.ts").read_text()

    def test_the_acknowledgement_payload_carries_perspective(self):
        # This endpoint is already fetched on every launch, so carrying it here
        # costs no extra request.
        assert '"perspective": basics.get(\'perspective\', \'self\')' in self.API

    def test_the_acknowledgement_payload_carries_the_patient_name(self):
        assert '"patient_name": basics.get(\'patient_name\')' in self.API
        assert "'patient_name': (patient.get('firstName') or None)" in self.STORAGE

    def test_the_shared_type_declares_both(self):
        assert "perspective?: 'self' | 'caregiver';" in self.TYPES
        assert "patient_name?: string | null;" in self.TYPES

    def test_holder_and_patient_names_are_distinct_fields(self):
        # Conflating them is the whole bug: on a caregiver account the holder is
        # not the patient.
        assert "account_holder_name?: string | null;" in self.TYPES
        assert "patient_name?: string | null;" in self.TYPES


class TestTheHelperCannotProduceBrokenGrammar:
    """"You have felt" and "Mary has felt" take different verbs. Any helper that
    drops a name into an arbitrary sentence eventually writes "Mary have felt"."""

    def test_pronouns_conjugate_like_you(self):
        # they/you share every conjugation used in the copy.
        for pair in ('"they\'ve" : "you\'ve"', '"they\'re" : "you\'re"'):
            assert pair in HELPER, pair

    def test_the_name_is_only_ever_possessive(self):
        # `${name}'s` is safe before a noun; a bare name before a verb is not.
        names = re.findall(r"\$\{name\}(.)", HELPER)
        assert names, "the name is never interpolated"
        assert set(names) == {"'"}, f"name used outside possessive position: {set(names)}"

    def test_a_missing_name_still_reads(self):
        # The name arrives a request later than the perspective does.
        assert "'their'" in HELPER and "'Their'" in HELPER

    def test_it_shares_the_existing_query(self):
        # A second request per screen for something already fetched at launch
        # would be a silly cost on a cellular connection in a waiting room.
        assert "queryKey: ['acknowledgement']" in HELPER


class TestPatientCopyFollowsThePerspective:
    """The strings the owner actually reported, plus their neighbours."""

    CASES = [
        ("app/(app)/index.tsx", "medical details"),
        ("app/(app)/care.tsx", "titleFor"),
        ("app/profile/index.tsx", "About"),
        ("app/tools/screening.tsx", "felt physically"),
        ("app/tools/trends.tsx", "check-ins are tracking"),
        ("components/chat/EscalationCard.tsx", "care team"),
    ]

    @pytest.mark.parametrize("rel,marker", CASES)
    def test_the_screen_reads_the_perspective(self, rel, marker):
        src = screen(rel)
        assert marker in src, f"{rel}: marker moved, update this test"
        assert "usePerspective" in src, f"{rel} still assumes the holder is the patient"

    def test_no_screen_still_hardcodes_add_my_medical_details(self):
        assert 'title="Add my medical details"' not in screen("app/(app)/index.tsx")

    def test_the_symptom_checkin_does_not_say_you(self):
        src = screen("app/tools/screening.tsx")
        assert "How you’ve felt physically" not in src
        assert "How you've felt physically" not in src

    def test_the_home_greeting_addresses_the_holder(self):
        # hero.first_name is the PATIENT's name. Greeting a caregiver with it
        # says "Hi Mary" to Mary's daughter.
        src = screen("app/(app)/index.tsx")
        assert "who.holderFirstName" in src


class TestAccountCopyIsLeftAlone:
    """The opposite failure. These belong to the person holding the account and
    must stay second person no matter who the app is about."""

    UNTOUCHED = [
        ("app/(auth)/login.tsx", "Forgot your password?"),
        ("app/settings/delete-account.tsx", "Delete my account permanently"),
        ("app/(onboarding)/state-restricted.tsx", "Delete my account"),
        ("app/settings/privacy.tsx", "Your rights"),
        ("app/tools/deep-research.tsx", "Your research question"),
    ]

    @pytest.mark.parametrize("rel,text", UNTOUCHED)
    def test_account_holder_copy_is_unchanged(self, rel, text):
        assert text in screen(rel), (
            f"{rel}: '{text}' belongs to the ACCOUNT HOLDER and must not follow "
            "the patient perspective")
