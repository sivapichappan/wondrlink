# learning_loop.py
"""
DORMANT: de-identified learning loop (Lifecycle Phase 5 — built, not active).

emit_pattern_record() is a hard no-op unless BOTH hold:
  1. FEATURE_MODEL_IMPROVEMENT=true (env, default false), and
  2. the user has affirmatively granted `consent_model_improvement`
     (an opt-IN key with no signup baseline — see supabase_storage.
     OPT_IN_CONSENT_KEYS / get_consent_status).

Activation is additionally gated on attorney review + a consent-version bump —
see docs/compliance/model_improvement_dormant.md for the checklist.

Record rules (enforced here, non-negotiable):
  - NO user_id, NO free text, NO dates. Cohort-keyed categorical fields only
    (cancer_slug | stage_group | topic buckets, coded values).
  - Every record passes detect_pii_leaks before insert.
  - k-anonymity at consumption: a pattern may only influence anything once
    >= K_ANONYMITY distinct contributions exist for its cohort_key.
"""

import logging
import os
from typing import Any, Dict

logger = logging.getLogger("learning_loop")

K_ANONYMITY = 20

# Whitelist of keys a pattern record may carry — everything else is dropped.
_ALLOWED_RECORD_KEYS = frozenset({
    "cancer_slug", "stage_group", "age_band", "register",
    "topic", "action", "treatment_class", "symptom_code",
    "temporal_bucket", "connection_strength", "outcome_code",
})


def _enabled() -> bool:
    return os.getenv("FEATURE_MODEL_IMPROVEMENT", "false").lower() == "true"


def emit_pattern_record(user_id: str, record: Dict[str, Any]) -> bool:
    """
    Emit one de-identified, cohort-keyed pattern record. Hard no-op while the
    feature is dormant or the user hasn't opted in. Never raises.
    """
    if not _enabled():
        return False
    try:
        from supabase_storage import get_consent_status
        status = get_consent_status(user_id)
        if not (status.get("consent_model_improvement") or {}).get("granted"):
            return False

        clean = {k: v for k, v in (record or {}).items()
                 if k in _ALLOWED_RECORD_KEYS and isinstance(v, (str, int, float, bool))}
        if not clean.get("cancer_slug") or not clean.get("topic"):
            return False

        from deidentify import detect_pii_leaks
        if detect_pii_leaks(clean):
            logger.warning("pattern record failed PII guard; dropped")
            return False

        cohort_key = f"{clean['cancer_slug']}|{clean.get('stage_group', 'unknown')}|{clean['topic']}"

        from supabase_client import get_admin_client
        get_admin_client().table("pattern_records").insert({
            "cohort_key": cohort_key,
            "record": clean,          # deliberately excludes user_id
        }).execute()
        return True
    except Exception as e:
        logger.warning(f"emit_pattern_record failed (non-fatal): {e}")
        return False
