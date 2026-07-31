#!/usr/bin/env python3
"""Provision a connection-map reviewer (SPEC §5.1, §5.2).

    python3 scripts/provision_reviewer.py --email dr@example.org \
        --name "Dr Jane Csiki" --credential MD --dry-run
    python3 scripts/provision_reviewer.py --email dr@example.org \
        --name "Dr Jane Csiki" --credential MD

ORDER MATTERS AND GETTING IT WRONG IS PERMANENT. The app's root gate checks
`is_reviewer` FIRST, but only sees it once the reviewer row exists. A physician
who signs up before being provisioned falls through into PATIENT onboarding, and
finishing that creates a patient profile — after which the database refuses to
make the account a reviewer, in both directions, by trigger. The only remedy is
deleting the account.

So this creates the auth account AND the reviewer row together, before she ever
opens the app. She then signs in and lands directly on the review queue.

The account is created already confirmed, so nothing is emailed and none of the
SMTP work has to be finished first.

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (production).
"""

import argparse
import os
import secrets
import sys
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

# §5.1: only a physician may attest. The database enforces it too
# (reviewer_attesting_is_physician_check); this fails earlier and more clearly.
PHYSICIAN_CREDENTIALS = ("MD", "DO")


def generate_password() -> str:
    """A password she changes on first sign-in. Long and random so a weak
    temporary credential never guards a signing account."""
    return secrets.token_urlsafe(18)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--credential", default="MD", choices=("MD", "DO", "NP", "PA", "PharmD", "RN", "other"))
    ap.add_argument("--role", default="reviewer_attesting",
                    choices=("observer", "reviewer_clinical", "reviewer_attesting", "admin"))
    ap.add_argument("--affiliation", default="external", choices=("internal", "external"))
    ap.add_argument("--cancer", default="breast")
    ap.add_argument("--password", default=None, help="omit to generate one")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.role == "reviewer_attesting" and args.credential not in PHYSICIAN_CREDENTIALS:
        print(f"ERROR: an attesting reviewer must be {' or '.join(PHYSICIAN_CREDENTIALS)}; "
              f"got {args.credential}")
        return 1

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return 1

    from supabase import create_client
    db = create_client(url, key)
    email = args.email.strip().lower()
    print(f"target: {url}\nreviewer: {args.name} <{email}> {args.credential} / {args.role}\n")

    # --- refuse if this address is, or ever was, a patient -----------------
    existing: Optional[Dict[str, Any]] = None
    page = db.auth.admin.list_users()
    users = page if isinstance(page, list) else getattr(page, "users", [])
    for u in users:
        if (getattr(u, "email", "") or "").lower() == email:
            existing = {"id": u.id}
            break

    if existing:
        prof = (db.table("patient_profiles").select("user_id")
                .eq("user_id", existing["id"]).execute()).data or []
        if prof:
            print("REFUSING: this address already holds a PATIENT profile.\n"
                  "  A reviewer account and a patient account are mutually exclusive and the\n"
                  "  database enforces it in both directions. Use a different address, or\n"
                  "  delete that account first if it was a test.")
            return 1
        print(f"account already exists ({existing['id'][:8]}), reusing it")

    already = (db.table("reviewer").select("id, status, role")
               .eq("email", email).execute()).data or []
    if already:
        print(f"reviewer row already exists: {already[0]}")
        return 0

    password = args.password or generate_password()

    if args.dry_run:
        print("(dry run) would create the auth account, then the reviewer row")
        return 0

    # --- 1. the auth account, pre-confirmed so no email is needed ----------
    if not existing:
        created = db.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        user_id = created.user.id
        print(f"auth account created: {user_id}")
    else:
        user_id = existing["id"]
        db.auth.admin.update_user_by_id(user_id, {"password": password})
        print(f"password reset on the existing account: {user_id}")

    # --- 2. the reviewer row ----------------------------------------------
    # The exclusivity trigger fires here on auth_user_id. If this raises, the
    # account is a patient and must not become a reviewer.
    row = (db.table("reviewer").insert({
        "auth_user_id": user_id,
        "email": email,
        "full_name": args.name,
        "credential": args.credential,
        "affiliation": args.affiliation,
        "role": args.role,
        "status": "active",
        "activated_at": "now()",
    }).execute()).data[0]
    print(f"reviewer row created: {row['id']}")

    # --- 3. what they may review ------------------------------------------
    db.table("reviewer_assignment").insert({
        "reviewer_id": row["id"],
        "cancer": args.cancer,
        "tiers": ["A", "B"],   # tier C has no attorney-approved wording yet (D2)
    }).execute()
    print(f"assignment: {args.cancer}, tiers A and B")

    print("\n" + "=" * 60)
    print("TEMPORARY PASSWORD (share over something other than email):")
    print(f"  {password}")
    print("=" * 60)
    print("\nShe signs in with that address and password. The root gate sees the")
    print("reviewer row and routes her straight to the review queue, never into")
    print("patient onboarding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
