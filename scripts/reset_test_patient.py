#!/usr/bin/env python3
"""Rewind a PATIENT test account so the persona arc can be replayed.

    python3 scripts/reset_test_patient.py --email <e> --dry-run
    python3 scripts/reset_test_patient.py --email <e> --full --clear-chat
    python3 scripts/reset_test_patient.py --email <e> --checkin-now
    python3 scripts/reset_test_patient.py --email <e> --to-sitting 6

WHY THIS EXISTS. docs/testing/persona-maria-alvarez.md walks one patient through
eight sittings, and three things in the product make that a one-shot experience:

  * The whole check-in rests 7 days, and each question rests 7 days on top of
    that. Sittings 5 and 8 are supposed to show TWO DIFFERENT question sets from
    the same bank, and without a time shift you would wait a week between them.
  * The getting-to-know-you question rests 3 turns and each topic 7 days.
  * A confirmed belief is permanent by design. Sitting 6 hands the tester a
    document belonging to someone else and asks them to save it ON PURPOSE, to
    see the damage. Without an undo, that is the end of the run.

So this is a time machine, not a repair tool.

IT WRITES THROUGH THE APP'S OWN FUNCTIONS, exactly like provision_patient.py.
--to-sitting replays each sitting's facts through `apply_confirmed_facts`, which
is what /api/report/apply calls, so a rewound account is byte-shaped like one
that scanned the documents. Hand-written rows drift from the real shape and then
the test is measuring the seeding.

IT REFUSES REVIEWER ACCOUNTS. Reviewer and patient are mutually exclusive by
database trigger in both directions, and a reviewer's chat runs on the sandbox
pipeline where none of this applies.

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
# BOTH, and the repo root matters: modules under lib/ import each other bare
# but lib/llm_utils.py also does "from lib.prompts import ...".
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "lib"))

from dotenv import load_dotenv

load_dotenv()

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# What each sitting TEACHES the app, as the belief paths the real path would
# write. Keyed by the sitting that produces them; --to-sitting N replays every
# entry with a key BELOW N, so the account arrives at sitting N knowing exactly
# what it would have known at that point and nothing more.
#
# These mirror docs/testing/documents/ one for one. When a document changes,
# change the matching block here, or the rewind stops matching the scan.
SITTING_FACTS: Dict[int, List[Dict[str, Any]]] = {
    # Sitting 2 scans the pathology report and the biomarker panel.
    2: [
        {"path": "primaryDiagnosis.site", "value": "breast"},
        {"path": "primaryDiagnosis.stage", "value": "Stage II"},
        {"path": "primaryDiagnosis.histology", "value": "Invasive ductal carcinoma"},
        {"path": "primaryDiagnosis.biomarkers.HER2", "value": "negative"},
        {"path": "primaryDiagnosis.biomarkers.PIK3CA", "value": "H1047R"},
        {"path": "primaryDiagnosis.biomarkers.BRAF", "value": "wild-type"},
    ],
    # Sitting 3 scans the oncology consultation note. The regimen string must
    # stay identical to the one in sitting 7 or the slug differs and sitting 7
    # appends a second chemo record instead of retiring this one.
    3: [
        {"path": "treatments.doxorubicin_and_cyclophosphamide_followed_by_paclitaxel",
         "value": {"regimen": "Doxorubicin and cyclophosphamide followed by paclitaxel",
                   "status": "active", "category": "Chemotherapy"}},
        {"path": "patient.comorbidities.hypothyroidism", "value": "hypothyroidism"},
    ],
    # Sitting 4 is the ZIP code, typed in chat, alone in its own message.
    4: [
        {"path": "patient.zipCode", "value": "78745"},
    ],
    # Sittings 5 and 6 teach the app nothing: the lab panel is display-only and
    # the wrong-name document is meant to be backed out of. They are listed so
    # the table reads as the whole arc rather than looking like an omission.
    5: [],
    6: [],
    # Sitting 7 scans the radiation summary: chemo retires, tamoxifen starts.
    # This is what swaps the check-in from nausea/eating/neuropathy to joint
    # aches and hot flashes.
    7: [
        {"path": "treatments.doxorubicin_and_cyclophosphamide_followed_by_paclitaxel",
         "value": {"regimen": "Doxorubicin and cyclophosphamide followed by paclitaxel",
                   "status": "completed", "category": "Chemotherapy"}},
        {"path": "treatments.whole_breast_radiation_with_a_tumor_bed_boost",
         "value": {"regimen": "Whole breast radiation with a tumor bed boost",
                   "status": "completed", "category": "Radiation"}},
        {"path": "treatments.tamoxifen_20_mg_daily",
         "value": {"regimen": "Tamoxifen 20 mg daily", "status": "active",
                   "category": "Other"}},
    ],
    8: [],
}

MAX_SITTING = max(SITTING_FACTS)


def _summarize(profile: Dict[str, Any]) -> Dict[str, Any]:
    """The handful of things worth reading back. Never prints a value that
    could identify anyone: this runs against a synthetic account, but the habit
    is the point."""
    patient = profile.get("patient") or {}
    dx = profile.get("primaryDiagnosis") or {}
    state = profile.get("model_state") or {}
    return {
        "stage": dx.get("stage"),
        "site": dx.get("site"),
        "histology": bool(dx.get("histology")),
        "biomarkers": sorted((dx.get("biomarkers") or {}).keys()),
        "zip_on_file": bool(patient.get("zipCode")),
        "treatments": [f"{t.get('regimen')} [{t.get('status') or 'active'}]"
                       for t in (profile.get("treatments") or [])],
        "beliefs": len(((profile.get("beliefs") or {}).get("fields") or {})),
        "lifecycle_stage": state.get("lifecycle_stage"),
        "last_check_in_at": state.get("last_check_in_at"),
        "check_in_log": len(state.get("check_in_log") or []),
        "asked_questions": len(state.get("asked_questions") or []),
        "turns_since_question": state.get("turns_since_question"),
    }


def _print_diff(before: Dict[str, Any], after: Dict[str, Any]) -> None:
    print("\n  what changes")
    for key in before:
        if before[key] != after.get(key):
            print(f"    {key}: {before[key]!r} -> {after.get(key)!r}")
    if before == after:
        print("    (nothing)")


def _resolve_user(db: Any, email: str) -> Optional[str]:
    page = db.auth.admin.list_users()
    for u in (page if isinstance(page, list) else getattr(page, "users", [])):
        if (getattr(u, "email", "") or "").lower() == email:
            return u.id
    return None


def _rebuild_from_fixture(user_id: str, fixture: str) -> Dict[str, Any]:
    """Reproduce exactly what provision_patient.py leaves behind, minus the
    auth/consent steps, which are already done and are not what a rewind is
    for."""
    from supabase_storage import save_profile, load_profile
    from patient_model import absorb_form_profile

    path = FIXTURES / f"{fixture}.json"
    if not path.exists():
        available = sorted(p.stem for p in FIXTURES.glob("*.json"))
        raise SystemExit(f"ERROR: no fixture '{fixture}'. Available: {', '.join(available)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("_comment", None)

    save_profile(user_id, data)
    stored = load_profile(user_id) or {}
    # MUTATES IN PLACE and returns a COUNT, not a profile. Assigning the return
    # value and saving it writes an integer over the profile.
    absorb_form_profile(stored, only_missing=True)
    save_profile(user_id, stored)
    return load_profile(user_id) or {}


def _apply_sittings(user_id: str, profile: Dict[str, Any], upto: int) -> int:
    """Replay every sitting strictly before `upto` through the app's own
    confirmed-fact writer."""
    from patient_model import apply_confirmed_facts

    applied = 0
    for sitting in sorted(SITTING_FACTS):
        if sitting >= upto:
            break
        facts = SITTING_FACTS[sitting]
        if facts:
            apply_confirmed_facts(user_id, profile, facts)
            applied += len(facts)
    return applied


def _clear_chat(db: Any, user_id: str, dry_run: bool) -> None:
    convs = (db.table("conversations").select("id", count="exact")
             .eq("user_id", user_id).execute())
    turns = (db.table("chat_turn").select("client_turn_id", count="exact")
             .eq("user_id", user_id).execute())
    n_conv = convs.count if convs.count is not None else len(convs.data or [])
    n_turn = turns.count if turns.count is not None else len(turns.data or [])
    print(f"  chat: {n_conv} conversation(s), {n_turn} in-flight turn row(s)")
    if dry_run:
        return
    db.table("conversations").delete().eq("user_id", user_id).execute()
    db.table("chat_turn").delete().eq("user_id", user_id).execute()
    print("  chat cleared")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rewind a patient test account so the persona arc can be replayed.")
    ap.add_argument("--email", required=True)
    ap.add_argument("--profile", default="breast_patient_partial",
                    help="fixture stem under scripts/fixtures/ (used by --full and --to-sitting)")
    ap.add_argument("--full", action="store_true",
                    help="back to the bare fixture: no biomarkers, treatments or ZIP")
    ap.add_argument("--to-sitting", type=int, default=None, metavar="N",
                    help=f"rewind to the state entering sitting N (1-{MAX_SITTING})")
    ap.add_argument("--checkin-now", action="store_true",
                    help="clear the check-in cooldowns so the card is offered again")
    ap.add_argument("--questions-now", action="store_true",
                    help="clear the gentle-question cooldowns")
    ap.add_argument("--clear-chat", action="store_true",
                    help="delete conversations and in-flight turn rows")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.full and args.to_sitting is not None:
        print("ERROR: --full and --to-sitting are two different rewinds; pick one.")
        return 1
    if args.to_sitting is not None and not (1 <= args.to_sitting <= MAX_SITTING):
        print(f"ERROR: --to-sitting takes 1-{MAX_SITTING}.")
        return 1
    if not any((args.full, args.to_sitting is not None, args.checkin_now,
                args.questions_now, args.clear_chat)):
        print("Nothing to do. Pass at least one of --full, --to-sitting, "
              "--checkin-now, --questions-now, --clear-chat.")
        return 1

    import os
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return 1

    email = args.email.strip().lower()
    from supabase import create_client
    db = create_client(url, key)
    print(f"target: {url}\naccount: <{email}>{'  (DRY RUN)' if args.dry_run else ''}\n")

    # Refuse anything that is, or ever was, a reviewer. Their chat runs on the
    # sandbox pipeline, where none of this state exists.
    reviewer = (db.table("reviewer").select("id").eq("email", email)
                .limit(1).execute()).data or []
    if reviewer:
        print("REFUSING: this address holds a REVIEWER row. Reviewer and patient\n"
              "  accounts are mutually exclusive and a reviewer's chat does not use\n"
              "  any of the state this script rewinds.")
        return 1

    user_id = _resolve_user(db, email)
    if not user_id:
        print("ERROR: no auth account for that address. Create one first:\n"
              f"  python3 scripts/provision_patient.py --email {email} --profile {args.profile}")
        return 1
    rev = (db.table("reviewer").select("id").eq("auth_user_id", user_id)
           .limit(1).execute()).data or []
    if rev:
        print("REFUSING: that account is already a reviewer.")
        return 1

    from supabase_storage import load_profile, save_profile

    original = load_profile(user_id) or {}
    before = _summarize(original)
    print("  before: " + json.dumps(before, default=str))

    if args.clear_chat:
        _clear_chat(db, user_id, args.dry_run)

    # --- the profile rewind ------------------------------------------------
    target_sitting = 1 if args.full else args.to_sitting
    if target_sitting is not None:
        if args.dry_run:
            # Model the outcome without writing: start from the fixture in
            # memory and replay the same facts the real path would.
            from patient_model import apply_confirmed_facts, absorb_form_profile
            path = FIXTURES / f"{args.profile}.json"
            projected = json.loads(path.read_text(encoding="utf-8"))
            projected.pop("_comment", None)
            absorb_form_profile(projected, only_missing=True)
            for sitting in sorted(SITTING_FACTS):
                if sitting >= target_sitting:
                    break
                if SITTING_FACTS[sitting]:
                    apply_confirmed_facts(user_id, projected, SITTING_FACTS[sitting])
            # model_state is rebuilt below; carry the parts a rewind keeps.
            projected["model_state"] = copy.deepcopy(original.get("model_state") or {})
            after = _summarize(projected)
        else:
            profile = _rebuild_from_fixture(user_id, args.profile)
            applied = _apply_sittings(user_id, profile, target_sitting)
            # A rewind puts the lifecycle stage back where the facts say it
            # belongs. It is monotonic in the product ON PURPOSE (a patient
            # never un-learns), so nothing but this script may lower it.
            state = profile.setdefault("model_state", {})
            state.pop("lifecycle_stage", None)
            save_profile(user_id, profile)
            label = "the bare fixture" if args.full else f"the state entering sitting {target_sitting}"
            print(f"  profile rebuilt to {label} ({applied} fact(s) replayed)")
            after = _summarize(load_profile(user_id) or {})
    else:
        after = dict(before)

    # --- the cooldowns -----------------------------------------------------
    # save_model_state re-reads the row and merges the check-in keys from it, so
    # clearing them means writing the WHOLE model_state back, not calling that
    # helper. Load fresh: the profile above may have just been rewritten.
    if args.checkin_now or args.questions_now:
        current = load_profile(user_id) or {}
        state = dict(current.get("model_state") or {})
        cleared = []
        if args.checkin_now:
            # Both halves matter: last_check_in_at gates the whole card, and
            # check_in_log rests each question id for 7 days on top of it.
            for key in ("last_check_in_at", "check_in_log"):
                if state.pop(key, None) is not None:
                    cleared.append(key)
        if args.questions_now:
            for key in ("asked_questions",):
                if state.pop(key, None) is not None:
                    cleared.append(key)
            # The gentle question is suppressed until this reaches the cooldown,
            # so it has to be set high, not deleted.
            state["turns_since_question"] = 99
            cleared.append("turns_since_question")
        print(f"  cooldowns cleared: {cleared or '(already clear)'}")
        if not args.dry_run:
            current["model_state"] = state
            save_profile(user_id, current)
            after = _summarize(load_profile(user_id) or {})
        else:
            projected = dict(after)
            projected.update({"last_check_in_at": None, "check_in_log": 0}
                             if args.checkin_now else {})
            projected.update({"asked_questions": 0, "turns_since_question": 99}
                             if args.questions_now else {})
            after = projected

    _print_diff(before, after)

    if args.dry_run:
        print("\n(dry run) nothing was written.")
    else:
        print("\nDone. The phone caches the profile, so pull to refresh or "
              "reopen the app before judging what you see.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
