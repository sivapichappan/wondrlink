#!/usr/bin/env python3
"""
One-time backfill for the multi-conversation display model.

Context: the `conversations`/`messages` tables already existed but were used
only as invisible LLM memory — every user has a single ('default', user_id)
conversation titled "Chat Session" that already holds their whole history
(because /api/chat has always written there via add_conversation). Promoting
these tables to the user-facing thread store therefore needs almost no data
copy — the history is already present. This script:

  1. RETITLES each default-named conversation ("Chat Session" / "New chat" /
     empty) from its first user message, so the drawer's Recents list shows a
     meaningful title instead of a generic one.
  2. REPORTS coverage: how many chat_messages rows (the legacy flat store the
     old mobile client wrote) lack a counterpart in `messages`. These are rare
     (a client save that never reached /api/chat's writer). Import is OFF by
     default and gated behind --import-orphans because a naive copy would
     DOUBLE history that is already in `messages`.

Idempotent: retitling only touches default-named conversations, so re-running
is safe. Non-destructive: chat_messages is never modified or deleted.

Usage:
    python scripts/backfill_conversations.py                   # dry-run report
    python scripts/backfill_conversations.py --apply           # retitle default convos
    python scripts/backfill_conversations.py --apply --limit 200
    python scripts/backfill_conversations.py --apply --import-orphans   # also import orphan chat_messages (deduped)

Prereqs:
    1. Apply supabase_migrations/2026_07_12_conversations_display.sql FIRST.
    2. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Make ./lib importable (mirrors scripts/migrate_profiles_v2.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_admin_client  # noqa: E402
from lib.supabase_storage import _derive_title  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_conversations")

DEFAULT_TITLES = {None, "", "Chat Session", "New chat"}


def _first_user_message(client, conversation_id: str) -> str | None:
    """The earliest user message content in a conversation, or None."""
    res = (
        client.table("messages")
        .select("content, role, sequence_number")
        .eq("conversation_id", conversation_id)
        .eq("role", "user")
        .order("sequence_number", desc=False)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0].get("content")
    return None


def retitle_conversations(client, apply: bool, limit: int) -> Dict[str, int]:
    """Retitle default-named conversations from their first user message."""
    convos = (
        client.table("conversations")
        .select("id, title, user_id")
        .limit(limit)
        .execute()
    ).data or []

    stats = {"scanned": len(convos), "needs_retitle": 0, "retitled": 0, "empty": 0}
    for c in convos:
        title = (c.get("title") or "").strip()
        if title not in {t for t in DEFAULT_TITLES if t}:  # only default-ish titles
            if title:  # already has a real title
                continue
        stats["needs_retitle"] += 1
        first = _first_user_message(client, c["id"])
        if not first:
            stats["empty"] += 1
            continue
        new_title = _derive_title(first)
        if apply:
            client.table("conversations").update({"title": new_title}).eq(
                "id", c["id"]
            ).execute()
            stats["retitled"] += 1
        else:
            logger.info(f"  [dry-run] {c['id'][:8]}… → '{new_title}'")
    return stats


def coverage_report(client) -> Dict[str, int]:
    """Count rows in each store to sanity-check before/after."""
    def _count(table: str) -> int:
        try:
            res = client.table(table).select("id", count="exact").limit(1).execute()
            return res.count or 0
        except Exception as e:
            logger.warning(f"  count({table}) failed: {e}")
            return -1

    return {
        "conversations": _count("conversations"),
        "messages": _count("messages"),
        "chat_messages": _count("chat_messages"),
    }


def import_orphans(client, apply: bool, limit: int) -> Dict[str, int]:
    """
    Import chat_messages rows that have NO matching `messages` row into the
    user's default conversation. Dedupe by (user_id, role, content) — because
    /api/chat already mirrors turns into `messages`, most rows are NOT orphans.
    """
    stats = {"scanned": 0, "imported": 0, "skipped_present": 0}
    cm = (
        client.table("chat_messages")
        .select("user_id, role, content, created_at")
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    ).data or []
    stats["scanned"] = len(cm)

    # Cache: does (user_id, content) already exist in messages?
    for row in cm:
        uid, role, content = row.get("user_id"), row.get("role"), row.get("content")
        if not uid or not content:
            continue
        existing = (
            client.table("messages")
            .select("id")
            .eq("user_id", uid)
            .eq("content", content)
            .limit(1)
            .execute()
        ).data
        if existing:
            stats["skipped_present"] += 1
            continue
        # Orphan: attach to the user's default conversation (create if absent).
        if apply:
            conv = (
                client.table("conversations")
                .select("id")
                .eq("user_id", uid)
                .eq("session_id", "default")
                .limit(1)
                .execute()
            ).data
            if conv:
                conv_id = conv[0]["id"]
            else:
                created = (
                    client.table("conversations")
                    .insert({"session_id": "default", "user_id": uid,
                             "title": _derive_title(content), "is_active": True})
                    .execute()
                ).data
                conv_id = created[0]["id"] if created else None
            if conv_id:
                seq = (
                    client.table("messages")
                    .select("id", count="exact")
                    .eq("conversation_id", conv_id)
                    .execute()
                ).count or 0
                client.table("messages").insert({
                    "conversation_id": conv_id, "user_id": uid, "role": role,
                    "content": content, "sequence_number": seq + 1,
                }).execute()
                stats["imported"] += 1
        else:
            stats["imported"] += 1  # would-import count in dry-run
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform writes (default: dry-run)")
    parser.add_argument("--limit", type=int, default=1000, help="max rows to scan")
    parser.add_argument("--import-orphans", action="store_true",
                        help="also import chat_messages rows missing from messages (deduped)")
    args = parser.parse_args()

    client = get_admin_client()
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info(f"=== backfill_conversations ({mode}) ===")

    before = coverage_report(client)
    logger.info(f"Coverage before: {before}")

    logger.info("\n-- Retitling default-named conversations --")
    rt = retitle_conversations(client, args.apply, args.limit)
    logger.info(f"Retitle stats: {rt}")

    if args.import_orphans:
        logger.info("\n-- Importing orphan chat_messages --")
        io = import_orphans(client, args.apply, args.limit)
        logger.info(f"Import stats: {io}")

    after = coverage_report(client)
    logger.info(f"\nCoverage after: {after}")

    if not args.apply:
        logger.info("\n(dry-run — no writes performed; re-run with --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
