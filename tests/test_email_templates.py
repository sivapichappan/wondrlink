"""Auth email templates (config/email_templates/).

Two things are worth a test here.

The first is load-bearing: `{{ .Token }}` is the ONLY reason these emails carry a
six digit code rather than a link, because Supabase chooses between the two on
template content alone. Both app screens ask for a code, so a template reverted to
the link form ships an email the user cannot act on, and nothing else in the
codebase would notice.

The second is that these are patient-facing copy and the project's copy rules
apply to them exactly as they apply to anything in the app.
"""

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from branding import APP_NAME  # noqa: E402

TEMPLATES = _REPO / "config" / "email_templates"
# All SIX Supabase email templates. The owner's rule is codes on phone and
# email, no links anywhere, so every template is listed and every one is held to
# the same check — not just the two the app calls today.
#
# Supabase's DEFAULTS for magic link, invite and change-email all contain
# {{ .ConfirmationURL }}. An unused template that sends a link is still a link
# that can be sent: by a stray call, by a future screen, or by an admin inviting
# someone from the dashboard. Reauthentication already defaults to a code and is
# written out anyway, because "five of six and the sixth is fine by default" is
# the kind of exception that quietly stops being true.
FILES = (
    "confirm_signup.html",
    "reset_password.html",
    "magic_link.html",
    "change_email.html",
    "invite.html",
    "reauthentication.html",
)


def raw(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def body(name: str) -> str:
    """The template Supabase renders: HTML comments removed, markup intact.

    Comments must come out before any placeholder is counted, because both files
    NAME the placeholders in their own comments to explain the code-versus-link
    rule. Markup stays in, so a `{{ .ConfirmationURL }}` hidden in an href is
    still caught.
    """
    return re.sub(r"<!--.*?-->", " ", raw(name), flags=re.DOTALL)


def visible(name: str) -> str:
    """The words a patient actually reads: comments and tags removed.

    Comments hold developer notes and are held to none of the copy rules.
    """
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body(name))).strip()


@pytest.mark.parametrize("name", FILES)
class TestCodeNotLink:
    def test_the_token_placeholder_is_present(self, name):
        assert "{{ .Token }}" in body(name), (
            f"{name} lost {{{{ .Token }}}}: Supabase would send a link, and the app "
            "asks for a code")

    def test_no_confirmation_url(self, name):
        # Having both is the subtle failure: Supabase sends the link form and the
        # code never appears, even though the placeholder is still in the file.
        assert "{{ .ConfirmationURL }}" not in body(name)

    def test_the_code_appears_exactly_once(self, name):
        assert body(name).count("{{ .Token }}") == 1


@pytest.mark.parametrize("name", FILES)
class TestPatientFacingCopy:
    def test_no_em_dashes(self, name):
        assert "—" not in visible(name)
        assert "–" not in visible(name)

    def test_product_name_matches_the_branding_constant(self, name):
        # The name cannot be imported into a dashboard-pasted template, so drift
        # is caught here instead.
        assert APP_NAME in visible(name)

    def test_the_app_store_name_is_not_used_in_copy(self, name):
        # "MySage" is the store listing only; the product calls itself Sage.
        assert "MySage" not in visible(name)

    def test_says_what_to_do_with_an_unexpected_email(self, name):
        """Someone who did not ask for this must be told what to do about it.

        NOT always "ignore it". For sign-up, sign-in and invite, ignoring really
        is safe and saying so calms the reader. For a CHANGE OF EMAIL ADDRESS or
        a REAUTHENTICATION, an unexpected message may be someone working on
        taking the account, and telling that reader to ignore it is bad advice —
        those two say not to enter the code and to change the password instead.

        So the property is "it tells you what to do", not "it contains the word
        ignore", which is what this asserted before the second kind existed.
        """
        text = visible(name).lower()
        assert "ignore" in text or "do not enter" in text, (
            f"{name} leaves an unexpected recipient with no instruction")

    def test_reading_level_is_plain(self, name):
        # Reuses the copy lint's grade estimator rather than a second one.
        sys.path.insert(0, str(_REPO / "lib" / "connection_map" / "review"))
        import copy_lint

        grade = copy_lint.reading_grade(visible(name))
        assert grade <= copy_lint.MAX_GRADE, f"{name} reads at grade {grade:.1f}"


class TestOperatorInstructions:
    """The dashboard steps and the SMTP limit only exist in the README, so an
    empty or truncated README is a real failure: nobody would know these have to
    be pasted in, or why delivery fails for testers."""

    README = (TEMPLATES / "README.md").read_text(encoding="utf-8")

    def test_uses_the_dashboard_row_labels_verbatim(self):
        # The reader is scanning a dashboard list for a matching row. Supabase
        # labels them "Confirm sign up", "Magic link or OTP" and so on; a README
        # that says "Confirm signup" or "Magic Link" sends them hunting.
        for label in ("Confirm sign up", "Reset password", "Magic link or OTP",
                      "Change email address", "Invite user", "Reauthentication"):
            assert label in self.README, f"dashboard label missing: {label}"

    def test_the_security_notifications_are_accounted_for(self):
        # A second group on the same page, seven emails, all off. They carry no
        # code so the codes rule does not reach them, but silence about them
        # reads as "these do not exist".
        assert "Security section is separate" in self.README
        assert "Password changed" in self.README

    def test_states_the_verify_types(self):
        # Getting these wrong is the most likely implementation mistake: 'email'
        # is the passwordless/magic-link type and fails against a signup token.
        assert "type: 'signup'" in self.README
        assert "type: 'recovery'" in self.README

    def test_warns_that_built_in_smtp_will_not_reach_testers(self):
        assert "Email address not authorized" in self.README
        assert "custom SMTP" in self.README

    def test_warns_that_confirm_email_must_be_on(self):
        assert "Confirm email" in self.README


class TestEveryTemplateIsCovered:
    """The rule is codes everywhere, so the rule has to bind every template that
    exists — including one added later by someone who did not read this file."""

    def test_no_template_file_escapes_the_checks(self):
        on_disk = {p.name for p in TEMPLATES.glob("*.html")}
        assert on_disk == set(FILES), (
            "a template file exists that the code-not-link checks do not cover: "
            f"{sorted(on_disk ^ set(FILES))}. Add it to FILES.")

    def test_all_six_supabase_templates_are_present(self):
        # Missing one does not fail loudly anywhere: the dashboard just keeps
        # its default, which for three of these sends a link.
        assert len(FILES) == 6

    def test_not_one_template_can_send_a_link(self):
        offenders = [n for n in FILES if "{{ .ConfirmationURL }}" in body(n)]
        assert not offenders, f"these would send a link: {offenders}"

    def test_every_template_carries_a_code(self):
        missing = [n for n in FILES if "{{ .Token }}" not in body(n)]
        assert not missing, f"these carry no code: {missing}"


class TestTakeoverRiskCopy:
    """The two templates that can signal an account takeover must not tell the
    reader to ignore it. Signing up, signing in and being invited are harmless
    to ignore; someone changing your email address is not."""

    TAKEOVER = ("change_email.html", "reauthentication.html")

    @pytest.mark.parametrize("name", TAKEOVER)
    def test_tells_the_reader_not_to_enter_the_code(self, name):
        assert "do not enter" in visible(name).lower()

    @pytest.mark.parametrize("name", TAKEOVER)
    def test_tells_the_reader_to_change_their_password(self, name):
        assert "password" in visible(name).lower()

    @pytest.mark.parametrize("name", TAKEOVER)
    def test_does_not_say_nothing_will_happen(self, name):
        # The harmless-flow reassurance would be false here.
        assert "nothing will happen" not in visible(name).lower()


class TestReadmeCoversEveryTemplate:
    """The dashboard steps live only here. A template the README does not name is
    a template nobody pastes in, which means it silently keeps the Supabase
    default — and three of those defaults send links."""

    README = (TEMPLATES / "README.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("name", FILES)
    def test_each_template_file_is_named(self, name):
        assert name in self.README

    def test_the_sequencing_hazard_is_written_down(self):
        # Shipping the app and the templates apart breaks sign-up in one
        # direction or the other, and neither failure is self-explanatory.
        assert "Order matters" in self.README
        assert "eas update" in self.README

    def test_existing_unconfirmed_accounts_are_flagged(self):
        # Turning Confirm email on is not a no-op for accounts that predate it.
        assert "Confirm email ON affects accounts that already exist" in self.README
