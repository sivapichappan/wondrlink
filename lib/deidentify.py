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
from typing import Dict, Any, Tuple
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

    return safe


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
# Runs over any payload about to leave the de-identification boundary
# (i.e. about to be sent to Together AI / Groq). Returns a list of
# matched patterns + offsets. Callers raise on any non-empty result.
#
# This is belt-and-suspenders: deidentify_conversation_context() already
# scrubs the conversation, but this catches anything that got injected
# into the system prompt, tool messages, profile fields the scrubber
# missed, etc.

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
