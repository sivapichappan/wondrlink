#!/usr/bin/env python3
"""Provision a PATIENT account for manual testing.

    python3 scripts/provision_patient.py --email tester@example.org \
        --profile breast_patient_partial --dry-run
    python3 scripts/provision_patient.py --email tester@example.org \
        --profile breast_patient_partial

WHY THIS EXISTS. The people who test Sage are also its connection-map reviewers,
and `mobile/hooks/useChat.ts` routes a reviewer's chat to /api/sandbox/chat — a
deliberately narrower pipeline with no verifier, no resources, no trial matching,
no question policy and no belief extraction. Testing the chat from a reviewer
account measures the wrong product. This makes a real patient account instead.

A SEPARATE SCRIPT FROM provision_reviewer.py, NOT A FLAG. Reviewer and patient
are mutually exclusive by database trigger in both directions, and the remedy for
getting it wrong is deleting the account. One script that can produce either
outcome is a foot-gun; two scripts that each refuse the other's case is not.

IT WRITES THROUGH THE APP'S OWN FUNCTIONS, never by hand. save_acknowledgement,
save_account_basics and save_profile are what /api/save_acknowledgement and
/api/account/basics call, so a seeded account is byte-shaped like one that walked
through onboarding — including the v2 universal-core columns and the belief
store. Hand-written rows drift from the real shape and then the test is
measuring the seeding, not the product.

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
# BOTH, and the repo root matters: modules under lib/ import each other bare
# ("from supabase_storage import ...") but lib/llm_utils.py also does
# "from lib.prompts import ...". With only lib/ on the path, save_profile's v2
# derivation dies with "No module named 'lib'" — and it dies INSIDE a try, so
# the profile still writes, just without cancer_slug. The account then looks
# fine and the app shows a cancer picker.
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "lib"))

from dotenv import load_dotenv

load_dotenv()

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Not a blocked state (IL and NV are), and not one that shows the AI-disclosure
# banner (CA, UT). The banner is correct behaviour; it is just noise on top of a
# test about answer quality.
DEFAULT_STATE = "TX"


def load_fixture(name: str) -> Dict[str, Any]:
    path = FIXTURES / f"{name}.json"
    if not path.exists():
        available = sorted(p.stem for p in FIXTURES.glob("*.json"))
        raise SystemExit(f"ERROR: no fixture '{name}'. Available: {', '.join(available) or 'none'}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--profile", default="breast_patient_partial",
                    help="fixture stem under scripts/fixtures/")
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--password", default=None, help="omit to generate one")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return 1

    profile = load_fixture(args.profile)
    email = args.email.strip().lower()
    first_name = ((profile.get("patient") or {}).get("firstName")
                  or (profile.get("patient") or {}).get("name") or "Tester")

    from supabase import create_client
    db = create_client(url, key)
    print(f"target: {url}\npatient: {first_name} <{email}>  fixture={args.profile}\n")

    # --- refuse if this address is, or ever was, a reviewer -----------------
    reviewer = (db.table("reviewer").select("id, status")
                .eq("email", email).limit(1).execute()).data or []
    if reviewer:
        print("REFUSING: this address already holds a REVIEWER row.\n"
              "  Reviewer and patient accounts are mutually exclusive and the database\n"
              "  enforces it in both directions. Use a different address.")
        return 1

    existing: Optional[str] = None
    page = db.auth.admin.list_users()
    for u in (page if isinstance(page, list) else getattr(page, "users", [])):
        if (getattr(u, "email", "") or "").lower() == email:
            existing = u.id
            break
    if existing:
        rev = (db.table("reviewer").select("id")
               .eq("auth_user_id", existing).limit(1).execute()).data or []
        if rev:
            print("REFUSING: that account is already a reviewer.")
            return 1
        print(f"account already exists ({existing[:8]}), reusing it")

    password = args.password or secrets.token_urlsafe(15)

    if args.dry_run:
        print("(dry run) would create the account, then consent, basics and profile")
        print(f"  state={args.state}  keys={sorted(profile.keys())}")
        return 0

    # --- 1. the auth account, pre-confirmed --------------------------------
    # Pre-confirmed because custom SMTP is not live yet, so a confirmation
    # email would never arrive.
    if existing:
        user_id = existing
        db.auth.admin.update_user_by_id(user_id, {"password": password,
                                                  "email_confirm": True})
        print(f"password reset on the existing account: {user_id}")
    else:
        user_id = db.auth.admin.create_user({
            "email": email, "password": password, "email_confirm": True,
        }).user.id
        print(f"auth account created: {user_id}")

    # --- 2. consent, so RootGate does not send them to the consent screen ---
    from compliance import CURRENT_CONSENT_VERSION, build_consent_metadata
    from supabase_storage import (
        save_acknowledgement, save_account_basics, save_profile, load_profile,
    )

    metadata = build_consent_metadata({
        "age_confirmed": True,
        "state": args.state,
        "consent_collection": True,
        "consent_sharing": True,
        "consent_terms": True,
    })
    metadata["cancer_slug"] = "breast" if "breast" in args.profile else None
    save_acknowledgement(user_id, consent_metadata=metadata,
                         consent_version=CURRENT_CONSENT_VERSION)
    print(f"consent recorded ({CURRENT_CONSENT_VERSION}, state {args.state})")

    # --- 3. basics, so needs_basics is false -------------------------------
    save_account_basics(user_id, "self", first_name,
                        patient_updates=profile.get("patient") or {})
    print("account basics saved")

    # --- 4. the profile ----------------------------------------------------
    # save_profile derives the v2 universal core, which is what sets
    # cancer_slug and therefore which overlay the model gets.
    save_profile(user_id, profile)

    # --- 5. absorb the form facts as confirmed beliefs ---------------------
    # Mirrors what /api/account/basics does, so the belief store starts in the
    # same state a real signup would leave it in. only_missing=True never
    # overwrites anything already there.
    try:
        from patient_model import absorb_form_profile
        stored = load_profile(user_id) or {}
        # MUTATES IN PLACE and returns a COUNT, not a profile. Assigning the
        # return value and saving it writes an integer over the profile.
        written = absorb_form_profile(stored, only_missing=True)
        save_profile(user_id, stored)
        print(f"beliefs absorbed: {written} confirmed field(s)")
    except Exception as e:  # noqa: BLE001
        print(f"note: belief absorption skipped ({e})")

    # --- 6. report what the app will actually see --------------------------
    # Read the slug the way the app does. It lives in its own COLUMN, not in
    # raw_profile, so reading it off the loaded profile always says None and
    # makes a correctly-seeded account look broken.
    from supabase_storage import get_cancer_slug
    slug = get_cancer_slug(user_id)
    print(f"\ncancer_slug resolved to: {slug or 'NONE — the app will show the cancer picker'}")
    if not slug:
        print("  ^ that is a FAILURE: the model would get the colorectal overlay.")
    stored = load_profile(user_id) or {}
    fields = ((stored.get("beliefs") or {}).get("fields") or {})
    print(f"beliefs on the account: {sorted(fields)}")
    if not stored.get("clinical"):
        print("note: `clinical` wrote empty. derive_clinical_payload is still")
        print("      colon-shaped and fails the breast enum. Nothing reads that")
        print("      column, so this is expected and harmless.")

    print("\n" + "=" * 60)
    print("PASSWORD (share over something other than email):")
    print(f"  {password}")
    print("=" * 60)
    print("\nSigning in should land straight on the home screen: no consent,")
    print("no who-for, no basics, no cancer picker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
