#!/usr/bin/env python3
"""
PII leak guard scope tests (offline — no LLM or Supabase calls).

Regression for the Jun 2026 "sleep schedule" incident: the route-level
guard scanned the fully assembled prompt, so public guideline chunks
containing publication dates ("05/12/2026") or site addresses
("Hackensack, NJ 07601") false-positive-blocked legitimate questions.

The guard now scans only the PHI-bearing components, which
assemble_prompt() exposes as metadata['pii_guard_payload'].

Run: python3 scripts/test_pii_guard.py
"""

import os
import sys
from typing import Any, Dict, List, Tuple

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'lib'))

from deidentify import detect_pii_leaks
from llm_utils import assemble_prompt

FAILURES: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def leak_names(leaks: List[Tuple[str, str]]) -> List[str]:
    return sorted({name for name, _snippet in leaks})


def build(message: str,
          retrieved: list,
          patient: Dict[str, Any],
          patient_context: Dict[str, Any],
          conversation: str = "") -> Tuple[str, dict]:
    return assemble_prompt(
        message, retrieved, patient,
        response_length="normal",
        conversation_context=conversation,
        patient_context=patient_context,
    )


# Public guideline chunk with a version date and a clinic address — the
# exact kind of text that used to trip the full-prompt scan.
DATED_CHUNK = {
    'content': (
        "Sleep disturbance and fatigue are common during treatment. "
        "Cognitive behavioral therapy for insomnia (CBT-I) is first-line. "
        "NCCN Guidelines Version 1.2026 — printed 05/12/2026. "
        "Survivorship clinic: 123 Main Street, Hackensack, NJ 07601."
    ),
    'filename': 'colon.pdf',
    'chunk_index': 42,
}

CLEAN_CONTEXT = {
    'diagnosis': 'colon cancer',
    'stage': 'Stage II',
    'current_treatments': ['FOLFOX'],
    'medical_history': ['hypertension'],
    'zip_code': '07450',  # must be stripped by deidentify_patient_context
}


def test_dated_public_chunk_not_blocked():
    print("\n1. Public guideline chunk with dates/address does NOT trip the guard")
    msg = "Tell me about my current state, how my sleep schedule should be looking like."
    prompt, meta = build(msg, [DATED_CHUNK], {}, dict(CLEAN_CONTEXT))

    payload = meta.get('pii_guard_payload')
    check("metadata exposes pii_guard_payload", payload is not None)
    check("payload has the four PHI-bearing components",
          payload is not None and
          set(payload.keys()) == {'message', 'patient_context', 'patient_profile', 'conversation_context'})

    payload_leaks = detect_pii_leaks(payload)
    check("payload scan is clean (request goes through)",
          payload_leaks == [], f"got {leak_names(payload_leaks)}")

    # Document the old behavior: the full prompt DOES contain the dated
    # chunk, so the pre-fix scan would have blocked this request.
    prompt_leaks = detect_pii_leaks(prompt)
    check("full-prompt scan still trips on the chunk (old behavior, why the fix exists)",
          len(prompt_leaks) > 0)

    check("zip_code stripped from payload patient_context",
          payload is not None and 'zip_code' not in payload['patient_context'])


def test_real_phi_in_profile_still_caught():
    print("\n2. Belt-and-suspenders: PHI smuggled through a free-text profile field is still caught")
    ctx = dict(CLEAN_CONTEXT)
    ctx['care_team_note'] = "Dr. Lee cell 555-867-5309, call after 5pm"
    _prompt, meta = build("What should I ask my oncologist?", [DATED_CHUNK], {}, ctx)
    leaks = detect_pii_leaks(meta['pii_guard_payload'])
    check("phone in patient_context flagged", 'phone' in leak_names(leaks),
          f"got {leak_names(leaks)}")


def test_message_pii_still_caught():
    print("\n3. PII typed directly in the user message is still caught")
    _prompt, meta = build("My SSN is 123-45-6789, can you save it?", [], {}, dict(CLEAN_CONTEXT))
    leaks = detect_pii_leaks(meta['pii_guard_payload'])
    check("ssn in message flagged", 'ssn' in leak_names(leaks),
          f"got {leak_names(leaks)}")


def test_conversation_scrubber_pipeline():
    print("\n4. Conversation scrubber neutralizes PII before the guard sees it")
    convo = "User: email me at jane.doe@example.com\nAssistant: I can't email you."
    _prompt, meta = build("What were we discussing?", [], {}, dict(CLEAN_CONTEXT), conversation=convo)
    payload = meta['pii_guard_payload']
    leaks = detect_pii_leaks(payload)
    check("email scrubbed from conversation (payload clean)",
          'email' not in leak_names(leaks), f"got {leak_names(leaks)}")
    check("conversation actually rewritten with [EMAIL] placeholder",
          '[EMAIL]' in payload['conversation_context'])


if __name__ == '__main__':
    print("PII leak guard scope tests")
    print("=" * 60)
    test_dated_public_chunk_not_blocked()
    test_real_phi_in_profile_still_caught()
    test_message_pii_still_caught()
    test_conversation_scrubber_pipeline()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"RESULT: {len(FAILURES)} FAILURE(S): {FAILURES}")
        sys.exit(1)
    print("RESULT: ALL PASS")
