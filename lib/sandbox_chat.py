"""The chat a reviewer tests on: a synthetic patient, in its own tables (§5.5).

WHY THIS IS NOT A BRANCH INSIDE /api/chat. A reviewer account may not hold a
patient profile — enforced by triggers in both directions since 2026_07_28. So
`/api/chat` cannot serve a reviewer even if it wanted to: `load_profile` returns
nothing, `get_or_create_conversation` would write a patient-scoped row, and the
extraction write-back would try to create a `patient_profiles` row the database
refuses. A flag inside that handler would be one forgotten branch away from a
physician's test message landing in patient data.

So the sandbox is a separate path over separate tables. The property §5.5 asks
for — "a reviewer session cannot open a chat bound to any patient_id where
is_synthetic = false" — is then true by construction rather than by a filter
somebody has to remember: there is no patient_id in this module at all.

WHAT A REVIEWER SEES, AND WHAT THEY DO NOT. This runs the patient-visible answer
path: the safety classifier, retrieval over the same guideline corpus, the same
prompt assembly, the same model, the same validation and tone pass. It does NOT
run the parts that exist to change a patient record over time — belief
extraction, the lifecycle question policy, the Modeler, trial matching. Those
act on a profile that accumulates, and a sandbox that accumulates state is a
sandbox that drifts away from what a new patient meets. A reviewer judging the
wording of an answer is judging exactly what a patient reads; a reviewer is not
judging the six-month arc of a profile, and this module should not pretend to
show them one.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("wondr-api")

# Long enough for a reviewer to probe a thread, short enough that the context
# never dominates the prompt. Patients get more because their history is the
# point; a test conversation is not.
SANDBOX_HISTORY_TURNS = 8

# What the synthetic patient is, when nothing has been written for this reviewer.
# A real-shaped profile, an obviously unreal person: the answers only exercise
# the pipeline honestly if there is a diagnosis behind them, and a physician
# must never wonder for a second whether they are looking at somebody's chart.
DEFAULT_SANDBOX_PROFILE: Dict[str, Any] = {
    "patient": {
        "firstName": "Sample",
        "name": "Sample Patient",
        "age": 54,
        "sex": "female",
    },
    "diagnosis": {
        "cancerType": "breast cancer",
        "stage": "II",
        "biomarkers": ["ER positive", "HER2 negative"],
    },
    "treatments": [
        {"name": "paclitaxel", "status": "active"},
    ],
    "comorbidities": [],
    "_synthetic": True,
}

DEFAULT_SANDBOX_CANCER = "breast"


def _client():
    from supabase_client import get_supabase_client
    return get_supabase_client()


# ---------------------------------------------------------------------------
# The synthetic patient
# ---------------------------------------------------------------------------
def get_sandbox_patient(reviewer_id: str) -> Optional[Dict[str, Any]]:
    """This reviewer's sandbox patient, creating it if the row is missing.

    Approval creates it in the same transaction as the activation, and the
    migration backfilled everyone already active, so this normally just reads.
    It self-heals anyway: a reviewer whose row went missing should meet a chat,
    not an error they cannot act on.
    """
    if not reviewer_id:
        return None
    client = _client()
    rows = (client.table("sandbox_patient")
            .select("id, raw_profile, cancer_slug")
            .eq("reviewer_id", reviewer_id)
            .limit(1)
            .execute()).data or []
    if rows:
        return rows[0]
    created = (client.table("sandbox_patient")
               .insert({"reviewer_id": reviewer_id})
               .execute()).data or []
    return created[0] if created else None


def sandbox_profile(patient_row: Dict[str, Any]) -> Dict[str, Any]:
    """The profile the pipeline sees. Never empty: a chat grounded on nothing
    answers generically, and a reviewer would be reviewing the wrong thing."""
    stored = patient_row.get("raw_profile") or {}
    if not stored:
        return dict(DEFAULT_SANDBOX_PROFILE)
    merged = dict(DEFAULT_SANDBOX_PROFILE)
    merged.update(stored)
    # Not overridable by whatever is in the column.
    merged["_synthetic"] = True
    return merged


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
def get_or_create_sandbox_conversation(sandbox_patient_id: str,
                                       conversation_id: Optional[str]) -> Optional[str]:
    client = _client()
    if conversation_id and conversation_id != "new":
        # Ownership check, same reason as the patient path: an id from the
        # client decides which rows get written.
        owned = (client.table("sandbox_conversation")
                 .select("id")
                 .eq("id", conversation_id)
                 .eq("sandbox_patient_id", sandbox_patient_id)
                 .limit(1)
                 .execute()).data or []
        if owned:
            return owned[0]["id"]
    created = (client.table("sandbox_conversation")
               .insert({"sandbox_patient_id": sandbox_patient_id,
                        "title": "Test conversation"})
               .execute()).data or []
    return created[0]["id"] if created else None


def sandbox_history(conversation_id: str) -> List[Dict[str, str]]:
    """Recent turns, oldest first, in the shape format_conversation_context wants."""
    if not conversation_id:
        return []
    client = _client()
    rows = (client.table("sandbox_message")
            .select("role, content")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(SANDBOX_HISTORY_TURNS * 2)
            .execute()).data or []
    rows.reverse()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def append_sandbox_turn(conversation_id: str, question: str, answer: str) -> None:
    if not conversation_id:
        return
    client = _client()
    client.table("sandbox_message").insert([
        {"conversation_id": conversation_id, "role": "user", "content": question},
        {"conversation_id": conversation_id, "role": "assistant", "content": answer},
    ]).execute()
    client.table("sandbox_conversation").update(
        {"updated_at": "now()"}).eq("id", conversation_id).execute()


def list_sandbox_conversations(sandbox_patient_id: str) -> List[Dict[str, Any]]:
    client = _client()
    return (client.table("sandbox_conversation")
            .select("id, title, created_at, updated_at")
            .eq("sandbox_patient_id", sandbox_patient_id)
            .order("updated_at", desc=True)
            .limit(50)
            .execute()).data or []


def reset_sandbox(sandbox_patient_id: str) -> None:
    """Throw the test conversations away. A reviewer probing an escalation path
    should not have to live with it at the top of their list afterwards."""
    client = _client()
    client.table("sandbox_conversation").delete().eq(
        "sandbox_patient_id", sandbox_patient_id).execute()
