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
        # The builder row died with the builder (change 2) and the tool grid
        # died when Home became the conversation (change 3); the anchor card
        # and the greeting carry Home's perspective copy now.
        ("app/(app)/index.tsx", "are they facing"),
        ("app/(app)/care.tsx", "titleFor"),
        ("app/profile/index.tsx", "About"),
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

    def test_the_check_in_asks_a_caregiver_about_the_patient(self):
        """The six questionnaires died with change 4 and check-ins became
        engine-chosen questions, but the bug they guarded against did not:
        "any tingling in YOUR fingers" asks the daughter about her own hands.
        The bank carries a written caregiver variant for every question,
        because these sentences have no mechanical rewrite that stays
        grammatical."""
        import json
        bank = json.loads((_REPO / "config" / "check_in" / "questions.json").read_text())
        for q in bank["questions"]:
            assert q.get("text_caregiver"), q["id"]
            assert "your" not in q["text_caregiver"].lower(), q["id"]
            if q.get("follow"):
                assert q.get("follow_caregiver"), q["id"]

    def test_the_check_in_endpoint_reads_the_perspective(self):
        api = (_REPO / "api" / "index.py").read_text()
        assert "select_check_in(profile, model_state, perspective=perspective)" in api

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


class TestSecureFieldsCannotBeAutocapitalised:
    """React Native's default autoCapitalize is "sentences", which uppercases the
    first character of a typed password. A password starting with a lowercase
    letter then cannot be entered on iOS at all, and the only feedback is
    "invalid email or password".

    This shipped: five secure fields across login, register and password reset,
    none setting autoCapitalize, while the email field beside them did. It was
    found when a real reviewer could not sign in with a correct password.
    """

    FIELD = (MOBILE / "components" / "ui" / "TextField.tsx").read_text()

    def test_the_primitive_defaults_secure_fields_to_no_autocapitalise(self):
        assert "rest.secureTextEntry" in self.FIELD
        assert "autoCapitalize: 'none' as const" in self.FIELD

    def test_it_also_disables_autocorrect_on_secure_fields(self):
        assert "autoCorrect: false" in self.FIELD
        assert "spellCheck: false" in self.FIELD

    def test_an_explicit_prop_still_wins(self):
        # The spread order is the whole contract: defaults first, caller last.
        assert self.FIELD.index("{...secureDefaults}") < self.FIELD.index("{...rest}")

    def test_it_is_fixed_in_the_primitive_not_at_each_call_site(self):
        # Five fields today; the sixth would forget it. Fixing it per-screen is
        # how this happened in the first place.
        secure_screens = [
            "app/(auth)/login.tsx",
            "app/(auth)/register.tsx",
            "app/(auth)/forgot-password.tsx",
        ]
        for rel in secure_screens:
            assert "secureTextEntry" in screen(rel), f"{rel}: no secure field found"


class TestPasswordRevealToggle:
    """Every password field can be revealed. Added after a correct password was
    rejected and there was no way to see what had actually been typed."""

    FIELD = (MOBILE / "components" / "ui" / "TextField.tsx").read_text()

    def test_the_toggle_lives_in_the_primitive(self):
        # One implementation, so every secure field has it and no screen has to
        # remember to add one.
        assert "setRevealed" in self.FIELD
        assert "Eye" in self.FIELD and "EyeOff" in self.FIELD

    def test_only_password_fields_get_a_toggle(self):
        assert "{isPassword && (" in self.FIELD

    def test_revealing_does_not_re_enable_autocapitalise(self):
        # The subtle one: the keyboard defaults must key off "is a password",
        # not off "is currently hidden", or revealing mid-entry would start
        # capitalising and reintroduce the bug this file already covers.
        assert "const secureDefaults = isPassword" in self.FIELD
        assert "const isPassword = !!rest.secureTextEntry;" in self.FIELD

    def test_the_toggle_owns_visibility_after_the_caller(self):
        # The caller says "this is a password"; the toggle says "hidden or not".
        # So the computed secureTextEntry must be applied AFTER {...rest}.
        assert self.FIELD.index("{...rest}") < self.FIELD.index("secureTextEntry={isPassword && !revealed}")

    def test_it_is_reachable_without_sight(self):
        assert "accessibilityRole=\"button\"" in self.FIELD
        assert "'Hide password' : 'Show password'" in self.FIELD

    def test_text_cannot_run_under_the_button(self):
        assert "paddingRight: isPassword ? REVEAL_HIT : 12" in self.FIELD

    def test_the_touch_target_is_big_enough(self):
        import re as _re
        m = _re.search(r"const REVEAL_HIT = (\d+)", self.FIELD)
        assert m and int(m.group(1)) >= 44, "iOS minimum touch target is 44pt"

    def test_the_visuals_are_not_in_a_pressed_style_function(self):
        # NativeWind silently strips visual styles from a Pressable's pressed
        # style FUNCTION, leaving a control that is invisible but still
        # tappable. The icon must sit on a static inner View.
        assert "style={{ position: 'absolute', right: 0, top: 0, bottom: 0 }}" in self.FIELD
