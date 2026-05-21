"""
Compliance constants and helpers (MHMDA, state restrictions, consent versioning).

Centralizes the regulatory configuration so updates flow through a single
location. Imported by:
  - api/index.py — register, acknowledgement, appeals endpoints
  - lib/supabase_storage.py — save_acknowledgement, delete audit log

DRAFT — ATTORNEY REVIEW REQUIRED for the legal positions encoded here.
"""

from typing import Dict, Any, Tuple


# =============================================================================
# CONSENT VERSIONING
# =============================================================================
# Bump this string when consent terms change. On next login any user whose
# stored consent_version is below the current one is forced through the
# extended re-consent modal (see Phase 3 in compliance plan).
CURRENT_CONSENT_VERSION = "v2-mhmda-2026-05"


# =============================================================================
# STATE-LEVEL POLICY
# =============================================================================
# States blocked at signup due to AI mental-health / behavioral-health
# legislation we do not currently comply with.
#   IL: WOPR Act (effective Aug 4, 2025) — forbids AI-delivered "therapy or
#       psychotherapy" without a licensed professional. WondrChat's screeners
#       (PHQ-9, GAD-7) + response generation could be argued in scope.
#   NV: AB 406 (effective Jul 1, 2025) — forbids AI mental/behavioral health
#       services that would constitute the practice of professional care.
BLOCKED_STATES = {"IL", "NV"}

# States with specific privacy regimes we comply with via the full opt-in flow.
# WA: My Health My Data Act (MHMDA) — private right of action, treble damages
#     up to $25k. Compliance handled via separate Consumer Health Data Privacy
#     Notice + three distinct opt-in consents.
MHMDA_STATES = {"WA"}


# =============================================================================
# REGIONAL GEOFENCE (Task 8)
# =============================================================================
# WondrLink v1 does not serve EU/EEA/UK/Swiss users. Servicing these
# regions requires a GDPR Article 30 RoPA, an EU Representative, SCCs
# in every sub-processor contract, and an EU AI Act risk-class
# determination — too much to build for v1.
#
# Detection: we read the CDN-supplied two-letter country code in
# x-vercel-ip-country (Vercel) — never trust client-side detection.
# Decision rationale: docs/compliance/eu_geofence_decision.md
BLOCKED_COUNTRIES = frozenset({
    # EU 27
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    # EEA additions
    "IS", "LI", "NO",
    # UK + Switzerland
    "GB", "CH",
})


def detect_country_code(headers) -> str:
    """Return the two-letter country code from CDN headers, or ''.

    Trust order:
      - x-vercel-ip-country (Vercel — set on every request from prod)
      - cf-ipcountry (Cloudflare — never used in prod, but kept for parity
        in case the deployment moves)
    """
    if not headers:
        return ""
    for key in ("x-vercel-ip-country", "X-Vercel-IP-Country",
                "cf-ipcountry", "CF-IPCountry"):
        value = headers.get(key) if hasattr(headers, "get") else None
        if value:
            return value.strip().upper()
    return ""


def is_blocked_country(country_code: str) -> bool:
    """Return True if the country code is in the geofence block list."""
    if not country_code:
        return False
    return country_code.strip().upper() in BLOCKED_COUNTRIES


def validate_country(headers) -> Tuple[bool, str, int]:
    """
    Reject signups originating from the EU/EEA/UK/Switzerland.

    Returns:
        (ok, error_message, http_status_code)
        - (True, "", 200)        : not in geofence
        - (False, msg, 451)      : in geofence (HTTP 451 — "Unavailable
                                   For Legal Reasons" matches the spec)
    """
    cc = detect_country_code(headers)
    if is_blocked_country(cc):
        return (
            False,
            "WondrLink is not currently available to residents of the EU, EEA, "
            "UK, or Switzerland. We're working on compliance with the applicable "
            "regulations (GDPR, EU AI Act) and hope to offer service in the "
            "future. Contact us at info@wondrlinkfoundation.org for updates.",
            451,
        )
    return True, "", 200


# US states + territories the dropdown accepts. "non_US" routes through a
# different consent message but still requires the three consents.
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",
}


def is_valid_state(state: str) -> bool:
    """Accept either a US state/territory code or the 'non_US' sentinel."""
    if not state:
        return False
    return state == "non_US" or state.upper() in US_STATES


def is_blocked_state(state: str) -> bool:
    """Returns True if the declared state cannot use WondrChat at this time."""
    if not state:
        return False
    return state.upper() in BLOCKED_STATES


# =============================================================================
# CONSENT VALIDATION
# =============================================================================
# All three opt-in consents are independently required (MHMDA: each consent
# must be a "clear affirmative act" — bundled acceptance is not compliant).
REQUIRED_CONSENT_FIELDS = (
    "consent_collection",   # collecting consumer health data
    "consent_sharing",      # sharing de-identified queries with LLM providers
    "consent_terms",        # ToU + Privacy Policy
)


def validate_consents(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate the three MHMDA-required consents are all true.

    Returns:
        (ok, error_message) — error_message is empty when ok=True.

    Each missing/false consent is reported individually so the UI can guide
    the user back to the right checkbox.
    """
    missing = []
    for field in REQUIRED_CONSENT_FIELDS:
        if not payload.get(field) is True:
            missing.append(field)
    if missing:
        labels = {
            "consent_collection": "data collection",
            "consent_sharing": "AI provider sharing",
            "consent_terms": "Terms of Use and Privacy Policy",
        }
        readable = " and ".join(labels[m] for m in missing)
        return False, f"All consents must be accepted to create an account (missing: {readable})."
    return True, ""


def validate_age_confirmation(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate the user's age via DOB.

    Authoritative server-side check — the client UI also blocks DOB picks
    that compute to < 18, but we re-validate here so a hand-crafted POST
    can't bypass the gate.

    Accepts either:
      - `date_of_birth`: "YYYY-MM-DD" — preferred; we compute age and reject < 18
      - `age_confirmed`: true (legacy clients during the DOB rollout window)

    On a valid DOB we return ok; the API layer is responsible for stripping
    the raw `date_of_birth` from any persisted record (we keep only the
    derived `age_band` + `is_adult` flag).
    """
    dob_str = payload.get("date_of_birth") or ""
    if dob_str:
        from datetime import date
        try:
            year, month, day = (int(x) for x in dob_str.split("-"))
            dob = date(year, month, day)
        except (ValueError, AttributeError):
            return False, "Please provide a valid date of birth."
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 0 or age > 130:
            return False, "Please provide a valid date of birth."
        if age < 18:
            return False, "You must be at least 18 years old to create an account."
        return True, ""

    # Legacy path during DOB rollout
    if payload.get("age_confirmed") is True:
        return True, ""

    return False, "You must confirm you are 18 years of age or older to create an account."


def compute_age_band(dob_str: str) -> str:
    """Return a coarse age band ('18-24', '25-34', ..., '75+') or '' on bad input.

    Used so we can persist a useful demographic bucket without storing the
    raw DOB (which would be a HIPAA identifier).
    """
    if not dob_str:
        return ""
    from datetime import date
    try:
        year, month, day = (int(x) for x in dob_str.split("-"))
        dob = date(year, month, day)
    except (ValueError, AttributeError):
        return ""
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 18:
        return ""
    if age < 25: return "18-24"
    if age < 35: return "25-34"
    if age < 45: return "35-44"
    if age < 55: return "45-54"
    if age < 65: return "55-64"
    if age < 75: return "65-74"
    return "75+"


def validate_state(state: str) -> Tuple[bool, str, int]:
    """
    Validate the declared state for signup/migration.

    Returns:
        (ok, error_message, http_status_code)
        - (True, "", 200)        : usable state
        - (False, msg, 400)      : missing or malformed
        - (False, msg, 422)      : valid but blocked (IL/NV) — distinct status
                                   so the frontend can show the right message
    """
    if not state:
        return False, "Please select your state of residence.", 400
    if not is_valid_state(state):
        return False, "Please select a valid US state, territory, or 'Outside the US'.", 400
    if is_blocked_state(state):
        return (
            False,
            "WondrChat is not currently available to residents of Illinois or Nevada "
            "due to state regulations governing AI in mental and behavioral health. "
            "We're working to expand access — thank you for your patience.",
            422,
        )
    return True, "", 200


def build_consent_metadata(
    payload: Dict[str, Any],
    ip_address: str = "",
) -> Dict[str, Any]:
    """
    Construct the consent_metadata JSONB payload persisted to
    user_acknowledgements.consent_metadata.

    Stores everything we need for an audit trail without storing PII beyond
    what's already required:
      - state self-declaration is not PII
      - age_band ('18-24', '25-34', ...) is demographically useful and not a
        HIPAA identifier
      - we deliberately do NOT store the raw date_of_birth — only the derived
        is_adult flag and the band
      - IP is hashed for fraud detection only
    """
    from datetime import datetime
    dob_str = payload.get("date_of_birth") or ""
    age_band = compute_age_band(dob_str) if dob_str else (payload.get("age_band") or "")
    return {
        "consent_version": CURRENT_CONSENT_VERSION,
        "age_confirmed": bool(payload.get("age_confirmed")),
        "age_band": age_band or None,
        "is_adult": bool(age_band) or bool(payload.get("age_confirmed")),
        "state": (payload.get("state") or "").upper() if payload.get("state") != "non_US" else "non_US",
        "consent_collection": bool(payload.get("consent_collection")),
        "consent_sharing": bool(payload.get("consent_sharing")),
        "consent_terms": bool(payload.get("consent_terms")),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "ip_hash": _hash_ip(ip_address) if ip_address else None,
    }


def _hash_ip(ip: str) -> str:
    """Hash IP for audit trail without storing the raw value."""
    import hashlib
    return hashlib.sha256((ip or "").encode("utf-8")).hexdigest()[:16]
