#!/usr/bin/env python3
"""Export a patient's chat threads to markdown, for reading a test run back.

    python3 scripts/export_conversation.py --email tester@example.org --all \
        --out ~/Desktop/sage-run-1.md
    python3 scripts/export_conversation.py --email tester@example.org \
        --conversation <uuid> --out ~/Desktop/thread.md

WHY THIS AND NOT A REPLAY SCRIPT. Re-asking the same fifty questions through the
API would produce DIFFERENT answers — temperature is 0.2-0.4, the ten-turn
conversation window differs, and the profile mutates as the chat learns. A
transcript of answers nobody saw is worse than no transcript: it invites
conclusions about a run that never happened. This is a pure read of what was
actually said.

Everything needed is already persisted. append_qa_to_conversation writes the
assistant row with the same metadata the client renders, plus the per-turn
diagnostics — query type, verifier verdict, retrieval confidence, tone
substitutions, whether the model was told the patient asked about the wrong
cancer. Those turn "answer 27 felt thin" into "answer 27 classified as general,
so it got the 250-token budget".

Writes OUTSIDE the repo by default and never logs the contents: a real thread is
patient data even when the patient is fictional.

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "lib"))

from dotenv import load_dotenv

load_dotenv()


def find_user(db, email: str) -> Optional[str]:
    page = db.auth.admin.list_users()
    for u in (page if isinstance(page, list) else getattr(page, "users", [])):
        if (getattr(u, "email", "") or "").lower() == email.lower():
            return u.id
    return None


def diagnostics(meta: Dict[str, Any]) -> str:
    """One compact line saying which machinery produced this answer."""
    if not isinstance(meta, dict):
        return ""
    debug = meta.get("debug_info") or {}
    bits: List[str] = []

    api = meta.get("api_used") or debug.get("api_used")
    if api:
        bits.append(str(api))
    qt = debug.get("query_type")
    if qt:
        bits.append(f"type={qt}")
    if meta.get("cancer_slug"):
        bits.append(f"cancer={meta['cancer_slug']}")

    sources = meta.get("sources") or []
    bits.append(f"{len(sources)} source{'' if len(sources) == 1 else 's'}")
    cites = sorted((meta.get("citations") or {}).keys())
    if cites:
        bits.append("cited " + ",".join(str(c) for c in cites))
        # A citation number with no matching source is the postprocess_citations
        # gap: it validates against the retrieved list, which is longer than the
        # list the model was actually shown.
        if any(int(c) > len(sources) for c in cites if str(c).isdigit()):
            bits.append("**CITATION OVER-RUN**")

    conf = (debug.get("retrieval_confidence") or {}).get("level")
    if conf:
        bits.append(f"retrieval={conf}")
    verdict = debug.get("verification") or debug.get("verified")
    if verdict is not None:
        bits.append(f"verify={verdict}")
    action = debug.get("recommended_action")
    if action and action != "pass":
        bits.append(f"**verifier={action}**")

    subs = (meta.get("tone") or {}).get("substitutions")
    if subs:
        bits.append(f"**tone rewrote {subs}**")
    if meta.get("mismatch_detected"):
        bits.append("**WRONG-CANCER NOTE SENT**")
    safety = (meta.get("safety") or {}).get("tier")
    if safety and safety != "NONE":
        bits.append(f"safety={safety}")
    if meta.get("clinical_trials"):
        bits.append("**trial cards replaced the answer**")
    if meta.get("pending_confirmations"):
        bits.append("confirmation chip")
    fu = meta.get("followups") or []
    if fu:
        bits.append(f"{len(fu)} follow-up chip{'' if len(fu) == 1 else 's'}")

    return " · ".join(bits)


def render(title: str, messages: List[Dict[str, Any]]) -> str:
    out = [f"## {title}", ""]
    turn = 0
    for msg in messages:
        role = msg.get("role")
        content = (msg.get("content") or "").rstrip()
        if role == "user":
            turn += 1
            out += [f"### {turn}. {content}", ""]
        elif role == "assistant":
            out += [content, ""]
            line = diagnostics(msg.get("metadata") or {})
            if line:
                out += [f"`{line}`", ""]
            res = (msg.get("metadata") or {}).get("resources") or []
            if res:
                out.append("resources: " + " · ".join(r.get("name", "?") for r in res))
                out.append("")
            out.append("---")
            out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--conversation", default=None)
    ap.add_argument("--all", action="store_true", help="every thread on the account")
    ap.add_argument("--out", default=None, help="default: ~/Desktop/sage-transcript.md")
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return 1
    if not args.conversation and not args.all:
        print("ERROR: pass --conversation <id> or --all")
        return 1

    from supabase import create_client
    from supabase_storage import get_conversation_messages, list_conversations

    db = create_client(url, key)
    user_id = find_user(db, args.email)
    if not user_id:
        print(f"ERROR: no account for {args.email}")
        return 1

    threads = ([{"id": args.conversation, "title": "Conversation"}]
               if args.conversation else list_conversations(user_id, limit=50))
    if not threads:
        print("no conversations on that account")
        return 1

    # Oldest first: a test run reads forward, not backward.
    threads = list(reversed(threads))

    parts = [f"# Sage transcript — {args.email}", ""]
    total = 0
    for t in threads:
        messages = get_conversation_messages(user_id, t["id"], limit=400)
        if not messages:
            continue
        total += sum(1 for m in messages if m.get("role") == "user")
        parts.append(render(t.get("title") or "Conversation", messages))

    out_path = Path(args.out).expanduser() if args.out else (
        Path.home() / "Desktop" / "sage-transcript.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")

    # Counts only — the file holds the conversation, the terminal does not.
    print(f"{total} question(s) across {len(threads)} thread(s) → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
