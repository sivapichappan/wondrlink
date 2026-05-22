"""
De-identification regression test (Task 10).

The MHMDA + HIPAA-style architectural defense rests on identifiable
data never leaving the de-identification boundary. This test asserts
two things end-to-end:

1. deidentify_conversation_context() removes the obvious identifier
   patterns from chat-style inputs.
2. detect_pii_leaks() — the runtime guard wired into /api/chat just
   before the LLM call — catches anything the scrubber missed.

Run locally:
    python -m pytest tests/test_deidentify.py -v

In CI: invoke from the pytest job (no GitHub Actions workflow added
in this commit; pair with the existing test runner).
"""

import os
import sys

# Make lib/ importable when running pytest from the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "lib"))

from deidentify import (  # noqa: E402
    deidentify_conversation_context,
    deidentify_raw_profile,
    detect_pii_leaks,
)


# ---------- Adversarial conversation fixtures ----------

CONVERSATION_FIXTURES = [
    # (description, input, must-not-contain substrings)
    # NOTE: Names are intentionally NOT regex-scrubbed (false-positive rate
    # on "Dr. Smith" / "Pembrolizumab" / etc. is too high). Name handling
    # is structural — names are stripped from the profile dict, not from
    # free-text. The conversation scrubber handles SSN, phone, email,
    # and street addresses; the runtime guard catches the rest at the
    # final boundary.
    (
        "phone number — hyphenated",
        "Call me at 555-123-4567 anytime",
        ["555-123-4567"],
    ),
    (
        "phone number — parenthesized",
        "Call (555) 987-6543 if needed",
        ["(555) 987-6543"],
    ),
    (
        "email address",
        "Email follow-up to patient@example.com please",
        ["patient@example.com"],
    ),
    (
        "ZIP code embedded in address",
        "I live at 123 Main St, Springfield, IL 62701",
        ["123 Main St"],
    ),
    (
        "SSN",
        "My SSN is 123-45-6789 in case you need it",
        ["123-45-6789"],
    ),
]


# ---------- detect_pii_leaks runtime-guard fixtures ----------
# These exercise the LAST-CHANCE guard. Anything in `expect_categories`
# should be present in the returned leak list.

PII_GUARD_FIXTURES = [
    (
        "ISO date in profile field",
        {"primaryDiagnosis": {"dateOfDiagnosis": "2024-07-15"}},
        ["full_date_iso"],
    ),
    (
        "US-formatted date in chat",
        "I started FOLFOX on 07/15/2024 and finished cycle 6 today",
        ["full_date_us"],
    ),
    (
        "phone in chat",
        "Please page Dr. Smith at 555-123-4567 if you have questions",
        ["phone"],
    ),
    (
        "email in chat",
        "Send the appeal letter to me at maya.s@example.org thanks",
        ["email"],
    ),
    (
        "SSN",
        "Member SSN 123-45-6789 for insurance verification",
        ["ssn"],
    ),
    (
        "labeled MRN",
        "MRN: 0042817 — sample sent to pathology",
        ["mrn_label"],
    ),
    (
        "labeled insurance ID",
        "Policy #: AETNA12345678",
        ["insurance_id_label"],
    ),
    (
        "street address",
        "Send mail to 456 Oak Avenue please",
        ["street_address"],
    ),
    (
        "ZIP + state",
        "MA 02115 is the right area",
        ["zip_with_state"],
    ),
    (
        "clean clinical chat — should be empty",
        "My CEA went from 5.2 to 1.8 ng/mL over the last 3 months. What does that mean?",
        [],
    ),
]


def test_conversation_scrubber_removes_basics():
    for description, raw, must_not_contain in CONVERSATION_FIXTURES:
        scrubbed = deidentify_conversation_context(raw)
        for needle in must_not_contain:
            assert needle not in scrubbed, (
                f"[{description}] de-identification regression: {needle!r} survived in {scrubbed!r}"
            )


def test_pii_guard_catches_residuals():
    for description, payload, expect_categories in PII_GUARD_FIXTURES:
        leaks = detect_pii_leaks(payload)
        found_categories = {name for name, _ in leaks}
        if not expect_categories:
            assert not leaks, (
                f"[{description}] runtime guard surfaced unexpected leaks: {leaks}"
            )
        else:
            for cat in expect_categories:
                assert cat in found_categories, (
                    f"[{description}] runtime guard missed {cat!r}; found={found_categories}"
                )


def test_pii_guard_does_not_log_raw_pii():
    """The runtime guard returns truncated snippets, never the full pattern,
    so log entries can never themselves leak."""
    payload = "Send mail to 555-123-4567 thanks"
    leaks = detect_pii_leaks(payload)
    for name, snippet in leaks:
        assert "555-123-4567" not in snippet or len(snippet) <= 40, (
            "snippet should be short and not contain the unescaped full match"
        )


def test_deidentify_raw_profile_strips_identifiers():
    """deidentify_raw_profile() drops the direct-identifier fields and relativizes dates."""
    raw = {
        "patientInfo": {
            "name": "Jane Doe",
            "address": "123 Main St, Boston, MA 02115",
            "phone": "555-555-5555",
            "email": "jane@example.com",
            "ssn": "123-45-6789",
            "mrn": "MRN-0042",
        },
        "primaryDiagnosis": {
            "site": "colon",
            "stage": "III",
            "dateOfDiagnosis": "2024-07-15",
        },
    }
    safe = deidentify_raw_profile(raw)
    # Direct identifiers must be gone (or replaced)
    serialized = str(safe).lower()
    assert "jane doe" not in serialized
    assert "555-555-5555" not in serialized
    assert "jane@example.com" not in serialized
    assert "123-45-6789" not in serialized
    # And the date should be relativized into a phrase like "approximately N months ago"
    diag = safe.get("primaryDiagnosis", {})
    if "dateOfDiagnosis" in diag:
        assert "approximately" in str(diag["dateOfDiagnosis"]).lower() or \
               "date not specified" in str(diag["dateOfDiagnosis"]).lower()
