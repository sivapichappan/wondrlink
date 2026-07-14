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
    check("payload has the five PHI-bearing components",
          payload is not None and
          set(payload.keys()) == {'message', 'patient_context', 'patient_profile',
                                  'conversation_context', 'connections_summary'})

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


def test_extractor_profile_context_hygiene():
    print("\n4. Profile-extraction LLM call never sees raw identifiers or bookkeeping")
    from llm_utils import _extraction_profile_context
    raw_profile = {
        'patient': {
            'firstName': 'Margaret', 'lastName': 'Okafor',
            'dob': '1961-03-14', 'zipCode': '94110',
            'age': 64, 'sex': 'Female',
        },
        'primaryDiagnosis': {'stage': 'Stage III', 'biomarkers': {'KRAS': 'G12D'}},
        '_sources': {'patient.age': {'source_type': 'chat', 'session_id': 'abc-123'}},
        'visit_recaps': [{'timestamp': '2026-07-01T10:00:00Z', 'transcript_preview': 'Dr. Chen said...'}],
    }
    ctx = _extraction_profile_context(raw_profile)
    check("name stripped from extractor context", 'Margaret' not in ctx and 'Okafor' not in ctx)
    check("dob/zip stripped from extractor context", '1961-03-14' not in ctx and '94110' not in ctx)
    check("_sources/visit_recaps stripped", '_sources' not in ctx and 'visit_recaps' not in ctx)
    check("clinical data preserved (stage, biomarker)", 'Stage III' in ctx and 'KRAS' in ctx)

    # Un-strippable PII smuggled in a free-text field -> context omitted entirely.
    leaky = {'patient': {'notes': 'call my nurse at 555-867-5309'}}
    check("leaky free-text profile context omitted", _extraction_profile_context(leaky) == '{}')


def test_conversation_scrubber_pipeline():
    print("\n5. Conversation scrubber neutralizes PII before the guard sees it")
    convo = "User: email me at jane.doe@example.com\nAssistant: I can't email you."
    _prompt, meta = build("What were we discussing?", [], {}, dict(CLEAN_CONTEXT), conversation=convo)
    payload = meta['pii_guard_payload']
    leaks = detect_pii_leaks(payload)
    check("email scrubbed from conversation (payload clean)",
          'email' not in leak_names(leaks), f"got {leak_names(leaks)}")
    check("conversation actually rewritten with [EMAIL] placeholder",
          '[EMAIL]' in payload['conversation_context'])


def test_modeler_payload_hygiene():
    print("\n6. Modeler input assembly: relativized + de-identified, guard aborts on poison")
    from datetime import datetime
    from modeler import assemble_modeler_input, ensure_connections

    now = datetime(2026, 7, 14, 12, 0, 0)
    clean_profile = {
        "patient": {"age": 62},
        "primaryDiagnosis": {"site": "colon", "stage": "Stage III"},
        "treatments": [{"regimen": "FOLFOX", "status": "active"}],
        "beliefs": {"version": 1, "pending": [], "fields": {
            "primaryDiagnosis.stage": {"value": "Stage III", "confidence": 1.0,
                                       "status": "confirmed", "source": "form", "history": []},
        }},
    }
    events = [{"kind": "belief_add", "path": "symptoms.fatigue",
               "payload": {"value": "fatigue"}, "source": "chat",
               "recorded_at": "2026-07-10T15:00:00"}]
    _payload, guard, _index = assemble_modeler_input(
        clean_profile, events, {}, [], [], ensure_connections({}), now)
    leaks = detect_pii_leaks(guard)
    check("clean relativized payload passes the guard",
          leaks == [], f"got {leak_names(leaks)}")
    check("timestamps rendered as day offsets, not ISO dates",
          "T-3d" in guard["timeline"] and "2026-07-10" not in guard["timeline"])

    # Poison must land in a section the payload actually serializes — a belief
    # value is the realistic leak path (free text that slipped past extraction).
    import copy
    poisoned = copy.deepcopy(clean_profile)
    poisoned["beliefs"]["fields"]["symptoms.notes"] = {
        "value": "call my nurse at 555-867-5309", "confidence": 0.6,
        "status": "provisional", "source": "chat", "history": [],
    }
    _payload2, guard2, _i2 = assemble_modeler_input(
        poisoned, events, {}, [], [], ensure_connections({}), now)
    leak_types = leak_names(detect_pii_leaks(guard2))
    check("poisoned belief value detected by the guard (run would abort)",
          any("phone" in t for t in leak_types), f"got {leak_types}")


if __name__ == '__main__':
    print("PII leak guard scope tests")
    print("=" * 60)
    test_dated_public_chunk_not_blocked()
    test_real_phi_in_profile_still_caught()
    test_message_pii_still_caught()
    test_extractor_profile_context_hygiene()
    test_conversation_scrubber_pipeline()
    test_modeler_payload_hygiene()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"RESULT: {len(FAILURES)} FAILURE(S): {FAILURES}")
        sys.exit(1)
    print("RESULT: ALL PASS")
