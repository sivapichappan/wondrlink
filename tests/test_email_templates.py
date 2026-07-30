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
FILES = ("confirm_signup.html", "reset_password.html")


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
        # Someone who did not ask for this needs to know it is safe to ignore.
        assert "ignore" in visible(name).lower()

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

    def test_names_both_supabase_templates(self):
        assert "Confirm signup" in self.README
        assert "Reset Password" in self.README

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
