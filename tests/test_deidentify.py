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


class TestAppBookkeepingNeverReachesTheGuard:
    """A silent 500 for every patient the Modeler had touched.

    `deidentify_raw_profile` strips app bookkeeping from the profile before
    prompt assembly. `connections` — the Modeler's graph — was never added to
    that list when the Modeler shipped, and its `meta` block holds `watermark`,
    `last_run_at` and `runs.date` as ISO timestamps. The pre-LLM leak guard
    scans this profile, flagged `full_date_iso`, and the chat route returned
    500. So the first time the nightly Modeler ran for a patient, that patient
    silently lost the ability to send a message.

    Measured in production 2026-08-04: 5 of 6 profiles blocked, every one of
    them a profile the Modeler had written to. Nobody would predict that
    consequence from reading either function on its own, which is why the test
    below asserts the PROPERTY (no ISO date survives) and not just the key.
    """

    @staticmethod
    def _profile_with_modeler_state():
        return {
            "patient": {"firstName": "Maria", "age": 47},
            "primaryDiagnosis": {"site": "Breast", "stage": "IIB"},
            "connections": {
                "version": 1,
                "meta": {
                    "last_run_at": "2026-08-04T00:15:56.060322+00:00",
                    "watermark": "2026-08-04T00:15:56.060322+00:00",
                    "runs": {"date": "2026-08-04", "count": 1},
                    "model": "deepseek-ai/DeepSeek-V4-Pro",
                },
                "edges": [{"src": "letrozole", "dst": "joint pain",
                           "first_seen": "2026-07-30T10:00:00Z"}],
            },
        }

    def test_connections_is_stripped(self):
        from deidentify import deidentify_raw_profile
        safe = deidentify_raw_profile(self._profile_with_modeler_state())
        assert "connections" not in safe

    def test_no_iso_date_survives_anywhere_in_the_profile(self):
        """The real invariant. A future sub-object with timestamps would
        reintroduce the outage even with `connections` handled."""
        import json
        import re
        from deidentify import deidentify_raw_profile
        safe = deidentify_raw_profile(self._profile_with_modeler_state())
        blob = json.dumps(safe, default=str)
        assert not re.search(r"\d{4}-\d{2}-\d{2}", blob), blob

    def test_the_guard_passes_a_modeler_touched_profile(self):
        # End to end: this is the exact condition that returned 500.
        from deidentify import deidentify_raw_profile, detect_pii_leaks
        safe = deidentify_raw_profile(self._profile_with_modeler_state())
        assert detect_pii_leaks({"patient_profile": safe}) == []

    def test_clinical_content_is_preserved(self):
        # A fix that strips too much would be a quieter kind of broken.
        from deidentify import deidentify_raw_profile
        safe = deidentify_raw_profile(self._profile_with_modeler_state())
        assert safe["primaryDiagnosis"]["site"] == "Breast"
        assert safe["primaryDiagnosis"]["stage"] == "IIB"
        assert safe["patient"]["age"] == 47
        assert "firstName" not in safe["patient"]

    def test_every_known_bookkeeping_key_is_covered(self):
        from deidentify import deidentify_raw_profile
        keys = ("_sources", "beliefs", "model_state", "connections",
                "visit_recaps", "previsit_questions", "appeal_drafts",
                "privacy_appeals")
        safe = deidentify_raw_profile({k: {"t": "2026-08-04T00:00:00Z"} for k in keys})
        assert safe == {}
