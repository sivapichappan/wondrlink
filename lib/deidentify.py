"""
HIPAA De-identification Module for WondrLink

Strips Protected Health Information (PHI) from patient context before
sending to external LLM APIs (Together AI, Groq) that lack BAA coverage.

Preserves all clinically relevant data:
- Cancer type, stage, histology
- Biomarkers (KRAS, MSI, BRAF, etc.)
- Treatment regimen, line, cycle number, toxicities
- Comorbidities and symptoms
- Performance status (ECOG)
- Age (but not DOB)
- Sex/gender (clinically relevant)

Strips HIPAA identifiers:
- Names, DOB, addresses, zip codes, phone, email, SSN
- Medical record numbers, account numbers
- Any other direct identifiers
"""

import re
import logging
from typing import Dict, Any, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def deidentify_patient_context(patient_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove PHI from patient_context dict before it enters prompt assembly.

    This is called AFTER extract_patient_context_complex() but BEFORE
    filter_relevant_context() and assemble_prompt().

    Args:
        patient_context: The extracted patient context dict

    Returns:
        A new dict with PHI stripped, clinical data preserved
    """
    if not patient_context:
        return patient_context

    # Create a copy to avoid mutating the original
    safe = dict(patient_context)

    # Strip direct identifiers
    safe.pop('patient_name', None)
    safe.pop('zip_code', None)

    # Keep age (derived from DOB, not identifying alone) but remove raw DOB if present
    safe.pop('dob', None)
    safe.pop('date_of_birth', None)

    # Keep race_ethnicity — clinically relevant for treatment response differences
    # (e.g., UGT1A1 polymorphisms more common in certain populations)
    # But strip if combined with other identifiers could be re-identifying
    # For now, keep it — it's a Safe Harbor "permitted" field when other identifiers removed

    return safe


def deidentify_raw_profile(patient: dict) -> dict:
    """
    Remove PHI from the raw patient profile dict before it enters prompt assembly.

    The raw profile is used in assemble_prompt() to access biomarkers and
    treatment data. This strips identifying fields while preserving clinical data.

    Args:
        patient: The raw patient profile JSON

    Returns:
        A new dict with PHI stripped
    """
    if not patient:
        return patient

    import copy
    safe = copy.deepcopy(patient)

    # Strip patient-level identifiers. The profile shape uses either
    # `patient` or `patientInfo` depending on the source (web signup vs.
    # legacy import); scrub both.
    for key in ('patient', 'patientInfo'):
        patient_info = safe.get(key, {})
        if isinstance(patient_info, dict):
            for field in (
                'name', 'firstName', 'lastName', 'fullName',
                'dob', 'dateOfBirth',
                'zipCode', 'zip_code', 'zip',
                'address', 'street', 'streetAddress',
                'phone', 'phoneNumber',
                'email', 'emailAddress',
                'ssn', 'socialSecurityNumber',
                'mrn', 'medicalRecordNumber',
                'insuranceId', 'memberId', 'policyNumber',
                'accountNumber',
            ):
                patient_info.pop(field, None)

    # Strip dates from surgical history (convert to relative timeframes)
    surgeries = safe.get('surgicalHistory', [])
    if isinstance(surgeries, list):
        for surgery in surgeries:
            if isinstance(surgery, dict) and 'date' in surgery:
                surgery['date'] = _relativize_date(surgery['date'])

    # Strip treatment start dates (convert to relative)
    treatments = safe.get('treatments', [])
    if isinstance(treatments, list):
        for tx in treatments:
            if isinstance(tx, dict) and 'startDate' in tx:
                tx['startDate'] = _relativize_date(tx['startDate'])

    # Strip diagnosis date (convert to relative)
    dx = safe.get('primaryDiagnosis', {})
    if isinstance(dx, dict) and 'dateOfDiagnosis' in dx:
        dx['dateOfDiagnosis'] = _relativize_date(dx['dateOfDiagnosis'])

    # Strip app bookkeeping sub-objects. These carry session ids, timestamps,
    # transcript previews, and (for beliefs/model_state) extraction provenance —
    # none of it is clinical context an LLM needs, and some of it is PHI-adjacent.
    #
    # `connections` (the Modeler's graph) belongs here and was missed when the
    # Modeler shipped, with a consequence nobody would predict from reading
    # this function: its `meta` block holds `watermark`, `last_run_at` and
    # `runs.date` as ISO timestamps, the pre-LLM leak guard scans this profile
    # and flags `full_date_iso`, and the CHAT ROUTE RETURNS 500. So the first
    # time the nightly Modeler ran for a patient, that patient stopped being
    # able to send a message at all. Measured 2026-08-04: 5 of 6 production
    # profiles blocked, every one of them a profile the Modeler had touched.
    #
    # Nothing loses data by this: every consumer of the graph (question policy,
    # trial ranking, the rendered summary) reads `connections` from the RAW
    # profile in the route, before de-identification. assemble_prompt receives
    # the summary as its own parameter and never reads the graph itself.
    for key in (
        '_sources', 'beliefs', 'model_state', 'connections',
        'visit_recaps', 'previsit_questions', 'appeal_drafts', 'privacy_appeals',
    ):
        safe.pop(key, None)

    return safe


# Whole-line identifier labels found on printed medical reports. Any line
# containing one of these is dropped entirely — the value beside the label
# (name, DOB, MRN, account number) is exactly what must never reach an LLM.
_REPORT_IDENTIFIER_LINE = re.compile(
    r'(?:patient\s*(?:name)?|name|dob|date\s+of\s+birth|birth\s*date|'
    r'mrn|medical\s+record|account\s*(?:#|no|number)|acct\s*#|'
    r'ssn|social\s+security|address|phone|encounter\s*(?:#|no|number)|'
    r'specimen\s+id|accession\s*(?:#|no|number))\s*[:#]',
    re.IGNORECASE,
)


def deidentify_report_text(text: str, profile: Optional[dict] = None) -> str:
    """
    De-identify OCR'd / PDF-extracted REPORT text before any external LLM call
    (the report-scan pipeline). Three passes:

      1. Drop whole lines that carry identifier labels (Patient:/DOB:/MRN:...)
         — printed reports put the value beside the label on the same line.
      2. Strip the user's own known identifiers from their profile
         (first name / name, dob, zip, phone), regex-escaped.
      3. The shared regex scrub (SSNs, phones, emails, dates, addresses).

    The endpoint runs detect_pii_leaks SEPARATELY afterwards and aborts on any
    residual hit — this function is the scrubber, the guard is the gate.
    """
    if not text:
        return text

    # Pass 1 — labeled identifier lines vanish entirely.
    kept_lines = [
        line for line in text.splitlines()
        if not _REPORT_IDENTIFIER_LINE.search(line)
    ]
    sanitized = "\n".join(kept_lines)

    # Pass 2 — the patient's own known identifiers.
    patient = (profile or {}).get('patient') or {}
    known_values = [
        patient.get('firstName'), patient.get('name'), patient.get('lastName'),
        patient.get('dob'), patient.get('zipCode'), patient.get('phone'),
    ]
    for value in known_values:
        value = str(value or '').strip()
        if len(value) >= 2 and value.lower() not in ('unknown', 'unspecified', 'none'):
            sanitized = re.sub(re.escape(value), '[REMOVED]', sanitized, flags=re.IGNORECASE)

    # Pass 3 — the shared pattern scrub.
    return deidentify_conversation_context(sanitized)


# --- Report patient-name mismatch (warn-never-block) ------------------------
# MUST run on the RAW report text BEFORE deidentify_report_text: pass 1 of the
# scrubber deletes the very identifier lines this reads. Output is a single
# boolean; names are never returned, logged, or stored.

# Line-start anchored so "Physician Name:" / "Inpatient:" / "Patient DOB:"
# never match. Bare "Name:" stays — LabCorp/Quest-style headers label the
# patient as just "Name: MARTINEZ, ROSA".
_PATIENT_NAME_LINE = re.compile(
    r"^\s*(?:patient(?:'?s)?(?:\s*name)?|pt\.?\s*name|name\s+of\s+patient|name)"
    r"\s*[:#]\s*(?P<value>.+)$",
    re.IGNORECASE,
)

# A candidate line containing any of these is a provider / third-party line,
# not the patient — skip it. A vetoed candidate means silence, and silence is
# the safe failure mode for a warn-only feature.
_PROVIDER_MARKERS = re.compile(
    r"\b(?:dr|m\.?d|d\.?o|physician|provider|ordering|referring|signed|"
    r"guarantor|insured|subscriber)\b",
    re.IGNORECASE,
)

_NAME_TOKEN_STOPLIST = frozenset(
    {"jr", "sr", "ii", "iii", "iv", "mr", "mrs", "ms", "miss", "dr", "md", "do"})


def _name_tokens(value: str) -> Set[str]:
    return {t for t in re.findall(r"[a-z]+", (value or "").lower())
            if len(t) >= 2 and t not in _NAME_TOKEN_STOPLIST}


def _tokens_match(a: str, b: str) -> bool:
    if a == b:
        return True
    # Prefix either direction covers nicknames (rob/robert); 2-char tokens
    # must match exactly.
    return min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a))


def report_name_mismatch(text: str, profile: Optional[dict] = None) -> bool:
    """
    True only when the report prints a patient name AND it shares no token with
    the profile's patient name. Compares against patient.firstName/name/lastName
    ONLY — for caregiver accounts patient.* is the care recipient (the person
    whose report it should be); the account holder's name must never be
    consulted. Any doubt -> False. Never raises, never logs.
    """
    try:
        report_tokens: Set[str] = set()
        for line in (text or "").splitlines():
            match = _PATIENT_NAME_LINE.match(line)
            if not match or _PROVIDER_MARKERS.search(line):
                continue
            # Truncate at a tab or 2+ spaces to shed merged table columns.
            value = re.split(r"\s{2,}|\t", match.group("value"))[0][:80]
            report_tokens |= _name_tokens(value)
        if not report_tokens:
            return False

        patient = (profile or {}).get('patient') or {}
        profile_tokens: Set[str] = set()
        for raw in (patient.get('firstName'), patient.get('name'), patient.get('lastName')):
            value = str(raw or '').strip()
            if len(value) >= 2 and value.lower() not in ('unknown', 'unspecified', 'none'):
                profile_tokens |= _name_tokens(value)
        if not profile_tokens:
            return False

        return not any(
            _tokens_match(r, p) for r in report_tokens for p in profile_tokens
        )
    except Exception:
        return False


def deidentify_conversation_context(conversation: str) -> str:
    """
    Scrub any PII that may have leaked into conversation history.

    Args:
        conversation: Formatted conversation context string

    Returns:
        Conversation with PII patterns replaced
    """
    if not conversation:
        return conversation

    sanitized = conversation

    # SSN patterns
    sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[ID REMOVED]', sanitized)

    # Phone patterns
    sanitized = re.sub(r'\b(?:\+1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE]', sanitized)

    # Email patterns
    sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized)

    # Street address patterns (number + street name)
    sanitized = re.sub(r'\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:St|Ave|Blvd|Dr|Rd|Ln|Ct|Way|Pl)\b\.?',
                       '[ADDRESS]', sanitized, flags=re.IGNORECASE)

    return sanitized


# =============================================================================
# PII LEAK DETECTOR (Task 10 — runtime assertion)
# =============================================================================
# Runs over the PHI-BEARING payload components about to leave the
# de-identification boundary (i.e. about to be sent to Together AI /
# Groq): the user message plus the de-identified patient context,
# profile, and conversation history. Returns a list of matched
# patterns + offsets. Callers raise on any non-empty result.
#
# This is belt-and-suspenders: deidentify_conversation_context() already
# scrubs the conversation, but this catches anything that got injected
# through profile fields or composition steps the scrubbers missed.
#
# SCOPE WARNING: do NOT run this over the fully assembled prompt.
# Retrieved guideline chunks are public documents whose publication
# dates ("05/12/2026") and clinic addresses ("Hackensack, NJ 07601")
# legitimately match the date/address patterns below — scanning them
# false-positive-blocks real questions (the Jun 2026 "sleep schedule"
# incident). Public corpus text cannot be PHI; only patient-sourced
# text crosses the boundary.

_PII_PATTERNS = [
    # SSN: 123-45-6789
    ("ssn", re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
    # Phone: 555-555-5555, (555) 555-5555, +1 555 555 5555
    ("phone", re.compile(r'\b(?:\+1[-.]?\s?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b')),
    # Email
    ("email", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    # MRN: typically labeled
    ("mrn_label", re.compile(r'\b(?:MRN|medical[\s-]?record[\s-]?(?:number|#))\s*[:=]?\s*\d{4,}\b', re.IGNORECASE)),
    # Insurance ID labeled
    ("insurance_id_label", re.compile(r'\b(?:insurance[\s-]?id|policy[\s-]?#|member[\s-]?id)\s*[:=]?\s*[A-Z0-9-]{5,}\b', re.IGNORECASE)),
    # ZIP+4 or 5-digit ZIP in an address context
    ("zip_with_state", re.compile(r'\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b')),
    # Full date YYYY-MM-DD
    ("full_date_iso", re.compile(r'\b(19|20)\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b')),
    # Full date MM/DD/YYYY
    ("full_date_us", re.compile(r'\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(19|20)\d{2}\b')),
    # Address: "123 Main St", "456 Oak Avenue", "789 Elm Blvd"
    ("street_address", re.compile(
        r'\b\d{1,5}\s+(?:[A-Z][a-z]+\s*){1,3}'
        r'(?:St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Dr(?:ive)?|Rd|Road|Ln|Lane|Ct|Court|Way|Pl(?:ace)?|Pkwy|Parkway)\b\.?',
        re.IGNORECASE
    )),
    # "My name is X" / "I'm X" — proper noun follows; loose, optional to enforce
    # We deliberately do NOT include name patterns in the runtime assertion
    # because the false-positive rate is high (every "Dr. Smith" reference
    # in clinical content would fire); name handling is structural.
]


def detect_pii_leaks(payload):
    """
    Scan a payload (str | list | dict) recursively for residual PII patterns.

    Returns:
        List of (pattern_name, snippet) tuples. Empty list = clean.

    Use as a final guard before sending to Together AI / Groq:
        leaks = detect_pii_leaks(prompt)
        if leaks:
            raise ValueError("PII leak detected", leaks)
    """
    leaks = []

    def _scan_text(text):
        if not isinstance(text, str):
            return
        for name, regex in _PII_PATTERNS:
            for m in regex.finditer(text):
                snippet = m.group(0)
                # Truncate snippet so the log entry never contains the full PII
                if len(snippet) > 40:
                    snippet = snippet[:18] + "…" + snippet[-12:]
                leaks.append((name, snippet))

    def _walk(value):
        if isinstance(value, str):
            _scan_text(value)
        elif isinstance(value, dict):
            for v in value.values():
                _walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                _walk(v)
        # numbers / bools / None — nothing to do

    _walk(payload)
    return leaks


def _relativize_date(date_str: str) -> str:
    """
    Convert an absolute date to a relative timeframe.

    '2024-07-10' → 'approximately 20 months ago'
    """
    if not date_str or date_str in ('unspecified', 'None', ''):
        return date_str

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        now = datetime.now()
        delta = now - date
        months = delta.days // 30

        if months < 1:
            return 'within the last month'
        elif months == 1:
            return 'approximately 1 month ago'
        elif months < 12:
            return f'approximately {months} months ago'
        else:
            years = months // 12
            remaining_months = months % 12
            if remaining_months == 0:
                return f'approximately {years} year{"s" if years > 1 else ""} ago'
            return f'approximately {years} year{"s" if years > 1 else ""} and {remaining_months} month{"s" if remaining_months > 1 else ""} ago'
    except (ValueError, TypeError):
        # If date parsing fails, remove it entirely
        return 'date not specified'
