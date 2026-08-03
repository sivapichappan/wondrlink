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


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_BATCH = 100          # Expo's documented maximum per request.
EXPO_TIMEOUT_SECONDS = 8  # A notification must never hold a request open.


def _send_expo(tokens: List[str], title: str, body: str,
               data: Dict[str, Any]) -> tuple:
    """POST to Expo's push service. Returns (delivered, dead_tokens).

    Plain urllib rather than exponent_server_sdk on purpose: this is one JSON
    POST, and the Vercel function bundle sits close to the 225 MB limit that
    .vercelignore exists to keep it under. A dependency for this would be a
    poor trade.

    Expo answers 200 even when individual messages fail, so the per-ticket
    statuses have to be read — treating the HTTP code as the answer would
    report every silent failure as a success.
    """
    import json as _json
    import urllib.request

    delivered = 0
    dead: List[str] = []

    for start in range(0, len(tokens), EXPO_BATCH):
        chunk = tokens[start:start + EXPO_BATCH]
        payload = [{"to": t, "title": title, "body": body, "data": data,
                    "sound": None, "priority": "high"} for t in chunk]
        req = urllib.request.Request(
            EXPO_PUSH_URL, data=_json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=EXPO_TIMEOUT_SECONDS) as resp:
                tickets = (_json.loads(resp.read().decode("utf-8")) or {}).get("data") or []
        except Exception:
            logger.warning("push send failed for a batch of %d", len(chunk))
            continue

        for token, ticket in zip(chunk, tickets):
            if not isinstance(ticket, dict):
                continue
            if ticket.get("status") == "ok":
                delivered += 1
                continue
            reason = ((ticket.get("details") or {}).get("error") or "")
            if reason == "DeviceNotRegistered":
                dead.append(token)
            else:
                # No token, no message text — this line goes to a log.
                logger.warning("push ticket error: %s", reason or "unknown")

    return delivered, dead


def _forget_tokens(user_id: str, tokens: List[str]) -> None:
    try:
        from supabase_client import get_admin_client
        client = get_admin_client()
        for token in tokens:
            (client.table("device_push_token").delete()
             .eq("user_id", user_id).eq("token", token).execute())
    except Exception:
        logger.debug("dropping dead push tokens failed", exc_info=True)


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
            # The in-app state is still the notification for anyone with no
            # device registered: the pending screen reads the reviewer status
            # on every launch, and that is not a fallback so much as the floor.
            logger.info("NOTIFY kind=%s delivery=in_app tokens=%d", kind, len(tokens))
            return result

        delivered, dead = _send_expo(tokens, title, body, data or {"kind": kind})
        result["delivered"] = delivered

        # A token Expo reports as unregistered belongs to an app that was
        # deleted or a permission that was revoked. Keeping it means retrying
        # forever against a device that will never answer.
        if dead:
            _forget_tokens(user_id, dead)
            result["dropped"] = len(dead)

        logger.info("NOTIFY kind=%s delivery=push tokens=%d delivered=%d dropped=%d",
                    kind, len(tokens), delivered, len(dead))
        return result
    except Exception:
        logger.exception("notify failed (continuing)")
        result["error"] = True
        return result
