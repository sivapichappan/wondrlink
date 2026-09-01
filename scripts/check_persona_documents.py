#!/usr/bin/env python3
"""Put every persona test document through the REAL report-scan path.

    python3 scripts/check_persona_documents.py            # deterministic gates only
    python3 scripts/check_persona_documents.py --llm      # + the real extractor call

WHY THIS EXISTS. A synthetic report is easy to write and easy to get wrong in
ways that are invisible until a phone is in your hand. Three failure modes have
teeth, and all three are silent:

  1. The PII guard 422s the WHOLE scan on one residual identifier, so a clinic
     footer like "Austin TX 78745" throws away a document that is otherwise
     perfect. The guard runs on the DE-IDENTIFIED text, so you cannot eyeball it.
  2. `validate_report_fact` drops any stage that is not exactly one of four
     strings. "Stage IIB" vanishes with no error anywhere, and the patient just
     never sees a stage to confirm.
  3. `report_name_mismatch` reads the RAW text before scrubbing. Whether the
     wrong-name trap actually fires depends on token matching rules you cannot
     guess from reading the document.

So each document declares what it is SUPPOSED to do and this asserts it, in the
same order the endpoint does. A document that fails here gets rewritten, not
shipped with a caveat.

The --llm pass is the only way to know whether the extractor really emits the
facts; everything before it only proves the document survives long enough to be
asked. It costs one extractor call per document.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "lib"))

from dotenv import load_dotenv

load_dotenv()

DOCS = _REPO / "docs" / "testing" / "documents"

# The profile the documents are scanned against. Mirrors
# scripts/fixtures/breast_patient_partial.json, which is what
# provision_patient.py writes -- report_name_mismatch and the scrubber's pass 2
# both read patient.* off exactly this shape.
PROFILE: Dict[str, Any] = {
    "patient": {"firstName": "Maria", "name": "Maria Alvarez", "age": 47, "sex": "Female"},
    "primaryDiagnosis": {"site": "Breast", "stage": "IIB"},
}

# What each document must do. `expect_paths` are belief paths that MUST survive
# validate_report_fact; `expect_values` pins the ones where the exact value is
# the whole point (the stage regex). `expect_labs` means display_only must be
# non-empty -- the review screen drops the name warning and shows "No medical
# facts found" when findings AND display_only are both empty, so a document with
# neither cannot be tested at all.
EXPECTATIONS: List[Dict[str, Any]] = [
    {
        "file": "01-pathology-lumpectomy.txt",
        "name_mismatch": False,
        "expect_paths": ["primaryDiagnosis.stage", "primaryDiagnosis.site",
                         "primaryDiagnosis.histology"],
        "expect_values": {"primaryDiagnosis.stage": "Stage II"},
        "expect_labs": False,
    },
    {
        "file": "02-biomarker-panel.txt",
        "name_mismatch": False,
        "expect_paths": ["primaryDiagnosis.biomarkers.HER2",
                         "primaryDiagnosis.biomarkers.PIK3CA"],
        "expect_values": {},
        "expect_labs": False,
        # ER, PR and Ki-67 are deliberately present and deliberately unwritable:
        # they are not in the eight-marker vocabulary. Assert they are DROPPED,
        # because a tester who sees them on the review card would be seeing a
        # regression in validate_report_fact.
        "forbid_path_fragments": ["ESTROGEN", "PROGESTERONE", "KI67", "KI-67", "ER", "PR"],
    },
    {
        "file": "03-oncology-consult.txt",
        "name_mismatch": False,
        "expect_paths": ["treatments.*", "patient.comorbidities.*"],
        "expect_values": {},
        "expect_labs": False,
        # The check-in bank matches substrings against the treatment's own
        # values, and only on ACTIVE records. Both halves are asserted below.
        "expect_treatment_active_terms": ["paclitaxel", "doxorubicin", "cyclophosphamide"],
        # The slug is derived from the regimen STRING, and documents 3 and 4
        # must produce the same one or document 4 appends a second chemo record
        # instead of retiring the first -- which leaves the chemo check-in
        # questions firing forever alongside the endocrine ones. This is why
        # neither document writes "(AC-T)" after the drug names: an optional
        # parenthetical is exactly the thing the extractor keeps on one run and
        # drops on the next.
        "expect_treatments": {
            "doxorubicin_and_cyclophosphamide_followed_by_paclitaxel": "active",
        },
        # Tamoxifen is discussed here but must NOT become an active record yet;
        # sitting 7 is where it starts, and an early active record would fire
        # the endocrine check-in questions months ahead of the arc.
        "forbid_active_treatment_terms": ["tamoxifen"],
    },
    {
        "file": "04-radiation-endocrine-summary.txt",
        "name_mismatch": False,
        "expect_paths": ["treatments.*"],
        "expect_values": {},
        "expect_labs": False,
        "expect_treatment_active_terms": ["tamoxifen"],
        "expect_treatments": {
            "doxorubicin_and_cyclophosphamide_followed_by_paclitaxel": "completed",
        },
        # A chemo term on the ACTIVE record would crowd out joint_aches and
        # hot_flashes: "Chemotherapy" contains "chemo", which wins slots 3 and 4
        # in bank order and consumes the 3-question budget.
        "forbid_active_treatment_terms": ["chemo", "paclitaxel", "doxorubicin"],
    },
    {
        "file": "05-lab-panel-abnormal.txt",
        "name_mismatch": False,
        "expect_paths": [],
        "expect_values": {},
        # Labs can ONLY be display_only. If this document ever produces a
        # finding, something started saving lab values.
        "expect_labs": True,
        "expect_no_findings": True,
    },
    {
        "file": "06-wrong-patient-addendum.txt",
        # The trap. Must warn, and must still carry a finding so the review
        # card renders at all -- an empty card drops the warning entirely.
        "name_mismatch": True,
        "expect_paths": ["primaryDiagnosis.biomarkers.HER2"],
        "expect_values": {},
        "expect_labs": False,
    },
]


def _fail(doc: str, message: str) -> Tuple[str, str]:
    return (doc, message)


def check_deterministic(doc: str, text: str, spec: Dict[str, Any]) -> List[Tuple[str, str]]:
    """The three gates that run before the LLM is ever called."""
    from deidentify import report_name_mismatch, deidentify_report_text, detect_pii_leaks

    failures: List[Tuple[str, str]] = []

    # Endpoint step 6: the name check runs on the RAW text, before scrubbing.
    warned = report_name_mismatch(text, PROFILE)
    if warned != spec["name_mismatch"]:
        failures.append(_fail(
            doc, f"name_mismatch is {warned}, expected {spec['name_mismatch']}"))

    # Endpoint step 7 + 8: scrub, then the guard aborts the whole scan on any
    # residual hit that is not a date.
    deid = deidentify_report_text(text[:8000], PROFILE)
    leaks = [name for name, _ in detect_pii_leaks(deid) if not name.startswith("full_date")]
    if leaks:
        failures.append(_fail(doc, f"PII GUARD WOULD 422 THE SCAN: {sorted(set(leaks))}"))

    # The scrubber deletes whole identifier lines. If it ate the clinical
    # content too, the document is unscannable no matter what the guard says.
    if len(deid.strip()) < 40:
        failures.append(_fail(doc, f"only {len(deid.strip())} chars survive scrubbing "
                                   "(the endpoint needs 40+)"))

    # The phone truncates to 8000 characters across at most 3 photographed
    # pages; anything past that is silently cut mid-report.
    if len(text) > 8000:
        failures.append(_fail(doc, f"{len(text)} chars, over the 8000 the phone sends"))

    return failures


def check_llm(doc: str, text: str, spec: Dict[str, Any]) -> List[Tuple[str, str]]:
    """The extractor call, then validate_report_fact on everything it returned."""
    from deidentify import deidentify_report_text
    from patient_model import extract_report_findings, validate_report_fact

    failures: List[Tuple[str, str]] = []
    deid = deidentify_report_text(text[:8000], PROFILE)
    result = extract_report_findings(deid, "breast")
    findings = result.get("findings") or []
    labs = result.get("display_only") or []

    validated: Dict[str, Any] = {}
    for f in findings:
        pair = validate_report_fact(f.get("path"), f.get("value"))
        if pair:
            validated[pair[0]] = pair[1]

    print(f"    findings kept: {sorted(validated) or '(none)'}")
    print(f"    labs shown:    {len(labs)}")
    dropped = len(findings) - len(validated)
    if dropped:
        print(f"    dropped by validate_report_fact: {dropped}")

    for path in spec.get("expect_paths") or []:
        if path.endswith(".*"):
            prefix = path[:-1]
            if not any(p.startswith(prefix) for p in validated):
                failures.append(_fail(doc, f"nothing under {path} survived validation"))
        elif path not in validated:
            failures.append(_fail(doc, f"{path} missing (extracted or dropped)"))

    for path, expected in (spec.get("expect_values") or {}).items():
        actual = validated.get(path)
        if actual != expected:
            failures.append(_fail(
                doc, f"{path} is {actual!r}, expected {expected!r} "
                     "(a stage that is not one of the four exact strings is dropped)"))

    for fragment in spec.get("forbid_path_fragments") or []:
        hits = [p for p in validated if p.rsplit(".", 1)[-1].upper() == fragment.upper()]
        if hits:
            failures.append(_fail(doc, f"{hits} survived validation but should not exist"))

    if spec.get("expect_no_findings") and validated:
        failures.append(_fail(doc, f"lab document produced saveable findings: {sorted(validated)}"))

    if spec.get("expect_labs") and not labs:
        failures.append(_fail(doc, "no display_only labs, so the review card cannot render"))

    # `_treatment_terms` in lib/check_in.py harvests values only from records
    # whose status is active/ongoing/absent, so build the same haystack it does.
    treatments = {p.split(".", 1)[1]: v for p, v in validated.items()
                  if p.startswith("treatments.") and isinstance(v, dict)}
    active_terms = " ".join(
        str(v).lower() for rec in treatments.values()
        if rec.get("status") in (None, "", "active", "ongoing")
        for v in rec.values()
    )
    if treatments:
        print("    treatments:   " + ", ".join(
            f"{slug} [{rec.get('status') or 'active'}]" for slug, rec in sorted(treatments.items())))

    for slug, status in (spec.get("expect_treatments") or {}).items():
        record = treatments.get(slug)
        if record is None:
            failures.append(_fail(
                doc, f"no treatment slug {slug!r} (got {sorted(treatments) or 'none'}); "
                     "documents 3 and 4 must agree or the second appends instead of retiring"))
        elif (record.get("status") or "active") != status:
            failures.append(_fail(
                doc, f"{slug} status is {record.get('status')!r}, expected {status!r}"))

    terms_wanted = spec.get("expect_treatment_active_terms") or []
    if terms_wanted:
        if not active_terms:
            failures.append(_fail(
                doc, "no ACTIVE treatment record; check_in skips every other status "
                     "and the trials context reads only status == 'active'"))
        missing = [t for t in terms_wanted if t not in active_terms]
        if missing:
            failures.append(_fail(
                doc, f"active treatment text is missing {missing}, so the intended "
                     "check-in questions cannot match"))

    forbidden = [t for t in (spec.get("forbid_active_treatment_terms") or [])
                 if t in active_terms]
    if forbidden:
        failures.append(_fail(
            doc, f"{forbidden} appear on an ACTIVE treatment record and will fire "
                 "check-in questions this sitting is not supposed to reach"))

    return failures


def check_artifact_drift() -> List[Tuple[str, str]]:
    """The artifact page carries each document inline so it can be photographed
    off a screen. That copy is what actually gets scanned, so it -- not the .txt
    -- is what these checks are really about. Assert they are the same bytes."""
    page = _REPO / "docs" / "testing" / "alvarez-folder.html"
    if not page.exists():
        return [_fail("alvarez-folder.html", "not found; the artifact page is the "
                                             "copy that gets photographed")]
    html = page.read_text(encoding="utf-8")
    failures: List[Tuple[str, str]] = []
    for spec in EXPECTATIONS:
        text = (DOCS / spec["file"]).read_text(encoding="utf-8").strip()
        if text not in html:
            failures.append(_fail(
                "alvarez-folder.html",
                f"the inline copy of {spec['file']} has drifted from the verified "
                "file; the page is what gets scanned, so fix the page"))
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true",
                    help="also run the real extractor (one call per document)")
    ap.add_argument("--only", default=None, help="substring of a filename")
    args = ap.parse_args()

    all_failures: List[Tuple[str, str]] = []
    for spec in EXPECTATIONS:
        doc = spec["file"]
        if args.only and args.only not in doc:
            continue
        path = DOCS / doc
        if not path.exists():
            all_failures.append(_fail(doc, "file not found"))
            continue
        text = path.read_text(encoding="utf-8")
        print(f"\n{doc}  ({len(text)} chars)")
        failures = check_deterministic(doc, text, spec)
        if args.llm and not failures:
            failures += check_llm(doc, text, spec)
        elif args.llm:
            print("    (skipping the extractor: a deterministic gate already failed)")
        for _, message in failures:
            print(f"    FAIL  {message}")
        if not failures:
            print("    ok")
        all_failures += failures

    if not args.only:
        drift = check_artifact_drift()
        print(f"\nartifact page: {'ok' if not drift else 'DRIFTED'}")
        for _, message in drift:
            print(f"    FAIL  {message}")
        all_failures += drift

    print("\n" + "=" * 62)
    if all_failures:
        print(f"{len(all_failures)} failure(s):")
        for doc, message in all_failures:
            print(f"  {doc}: {message}")
        return 1
    print("all documents pass" + ("" if args.llm else " (deterministic gates only; "
                                                      "add --llm for the extractor)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
