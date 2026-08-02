"""Telling someone something happened while they were not looking.

PUSH-READY, NOT PUSH-ENABLED. Delivery to a phone needs `expo-notifications`,
which is a native module: it needs a real EAS build, an app-version bump, and
Apple Developer portal access to mint an APNs key. An over-the-air update
carrying a native module to an installed build fatals on launch (see
`.claude/rules/mobile-ui.md` on Metro's guardedLoadModule). So push ships in its
own wave with its own binary gate.

What exists now is the CALL SITE and the token table. `notify()` records the
delivery attempt and returns; when the native side lands, the send goes in here
and nothing else in the codebase moves. The alternative — adding the call sites
later — means going back through approval, publication and escalation paths
looking for the places that should have notified, which is how a notification
quietly never gets sent.

The wave-1 notification a reviewer actually receives is the pending screen in
the app: they applied, they see where it stands, and the next time they open it
they are in. That is deliberately not nothing.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("wondr-api")

# Flipped on in wave 2, with the build that carries the native module. Read
# directly from the environment with a false default, per the repo rule on
# dormant flags: feature_enabled() defaults TRUE and must never gate one.
PUSH_ENABLED = os.environ.get("FEATURE_PUSH_NOTIFICATIONS", "").lower() == "true"

# Kinds are named here rather than passed as free strings so the set stays
# countable — a notification nobody can enumerate is a notification nobody can
# turn off.
KIND_REVIEWER_APPROVED = "reviewer_approved"
KIND_REVIEWER_REJECTED = "reviewer_rejected"

# Copy lives with the kind. Patient-facing rules do not apply to these (they go
# to clinicians, not patients), but the plain-language habit does.
_COPY: Dict[str, Dict[str, str]] = {
    KIND_REVIEWER_APPROVED: {
        "title": "You are approved",
        "body": "Your reviewer access is active. Open the app to start.",
    },
    KIND_REVIEWER_REJECTED: {
        "title": "About your reviewer request",
        "body": "There is an update on your request. Open the app to read it.",
    },
}


def get_push_tokens(user_id: str) -> List[str]:
    """Every device this account has registered. Empty until wave 2 writes any."""
    if not user_id:
        return []
    try:
        from supabase_client import get_admin_client
        rows = (get_admin_client().table("device_push_token")
                .select("token")
                .eq("user_id", user_id)
                .execute()).data or []
        return [r["token"] for r in rows if r.get("token")]
    except Exception:
        # A missing table (migration not yet applied) or a transient failure
        # must never take down the thing that was trying to notify.
        logger.debug("push token lookup failed", exc_info=True)
        return []


def notify(user_id: str, kind: str,
           title: Optional[str] = None,
           body: Optional[str] = None,
           data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send a notification, or record that one was due.

    NEVER RAISES. Every caller is doing something more important than notifying
    — approving a reviewer, publishing a version — and a failed notification
    must not roll that back. The result dict says what happened so a caller that
    cares can log it.

    No PHI in `title`, `body` or `data`: a notification renders on a lock screen.
    """
    result: Dict[str, Any] = {"kind": kind, "delivered": 0, "enabled": PUSH_ENABLED}
    try:
        copy = _COPY.get(kind, {})
        title = title or copy.get("title") or "Sage"
        body = body or copy.get("body") or ""

        tokens = get_push_tokens(user_id)
        result["tokens"] = len(tokens)

        if not PUSH_ENABLED or not tokens:
            # The in-app state IS the notification today: the pending screen
            # reads the reviewer status on every launch.
            logger.info("NOTIFY kind=%s delivery=in_app tokens=%d", kind, len(tokens))
            return result

        # Wave 2 fills this in (exponent_server_sdk against `tokens`). Left as an
        # explicit branch rather than a TODO comment so the flag has somewhere to
        # be true.
        logger.info("NOTIFY kind=%s delivery=push tokens=%d", kind, len(tokens))
        result["delivered"] = 0
        return result
    except Exception:
        logger.exception("notify failed (continuing)")
        result["error"] = True
        return result
