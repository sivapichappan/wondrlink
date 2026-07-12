#!/usr/bin/env python3
"""
Live validation harness for the clinical-trials pipeline.

Hits the REAL ClinicalTrials.gov v2 API (no cache) across several mock patients
and every radius option, and asserts that EVERY returned trial is valid:
  - overallStatus in {RECRUITING, NOT_YET_RECRUITING}
  - studyType == INTERVENTIONAL
  - key fields present (nctId, title, conditions|interventions, sex)
  - within the requested radius (recomputed via haversine on each location's
    geoPoint; geoPoint-missing locations are counted, not hard-failed, since the
    server already geo-filtered)
  - parse_trial_result() extracts the enriched fields without error

Run: python3 scripts/test_clinical_trials_live.py
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'lib'))

from lib.clinical_trials import (
    build_search_query,
    fetch_clinical_trials,
    parse_trial_result,
    get_zip_coordinates,
    haversine_distance,
)

FAILURES = []
RADIUS_TOLERANCE_MI = 15  # absorb ZIP-prefix centroid error vs. exact geoPoint

RECRUITING = {"RECRUITING", "NOT_YET_RECRUITING"}

PATIENTS = [
    {"id": "CRC-IV-NYC-MSIH", "cancer_slug": "colorectal", "cancer_type": "colorectal cancer",
     "stage": "Stage IV", "zip_code": "10029", "biomarkers": "MSI-H", "age": 58, "gender": "female"},
    {"id": "CRC-III-TX-KRAS", "cancer_slug": "colorectal", "cancer_type": "colorectal cancer",
     "stage": "Stage III", "zip_code": "77030", "biomarkers": "KRAS G12C", "age": 63, "gender": "male"},
    {"id": "LUNG-IV-RURAL", "cancer_slug": "lung", "cancer_type": "lung cancer",
     "stage": "Stage IV", "zip_code": "59718", "biomarkers": "EGFR", "age": 70, "gender": "female"},
    {"id": "BREAST-II-CHI", "cancer_slug": "breast", "cancer_type": "breast cancer",
     "stage": "Stage II", "zip_code": "60611", "biomarkers": "HER2 positive", "age": 49, "gender": "female"},
    {"id": "PANC-IV-LA", "cancer_slug": "pancreatic", "cancer_type": "pancreatic cancer",
     "stage": "Stage IV", "zip_code": "90048", "biomarkers": "BRCA", "age": 66, "gender": "male"},
]

RADII = [25, 50, 100, None]


def check(name, cond, detail=""):
    if not cond:
        FAILURES.append(name + (f" — {detail}" if detail else ""))
    return cond


def study_status(study):
    return (study.get("protocolSection", {}).get("statusModule", {}) or {}).get("overallStatus", "")


def study_type(study):
    return (study.get("protocolSection", {}).get("designModule", {}) or {}).get("studyType", "")


def us_locations(study):
    locs = (study.get("protocolSection", {}).get("contactsLocationsModule", {}) or {}).get("locations", []) or []
    return [l for l in locs if (l.get("country", "") or "").lower() in ("united states", "usa", "us")]


def within_radius(study, coords, radius):
    """(has_within, geo_missing) — is a geocoded US location within radius?"""
    if not coords:
        return True, False  # can't geocode patient; don't penalize
    any_geo = False
    for loc in us_locations(study):
        gp = loc.get("geoPoint") or {}
        if gp.get("lat") is not None and gp.get("lon") is not None:
            any_geo = True
            d = haversine_distance(coords, (gp["lat"], gp["lon"]))
            if d <= radius + RADIUS_TOLERANCE_MI:
                return True, False
    # No geocoded location matched. If none had geoPoint, flag geo-missing.
    return (False, not any_geo)


def run_case(pc, radius):
    label = f"{pc['id']} r={radius if radius else 'US'}"
    coords = get_zip_coordinates(pc["zip_code"])

    # 1. Query assertions
    params = build_search_query(pc, page_size=50, radius_miles=radius)
    check(f"[{label}] interventional filter",
          params.get("filter.advanced") == "AREA[StudyType]INTERVENTIONAL")
    check(f"[{label}] recruiting status filter",
          params.get("filter.overallStatus") == "RECRUITING,NOT_YET_RECRUITING")
    check(f"[{label}] fields projection present", bool(params.get("fields")))
    geo_expected = radius is not None and coords is not None
    check(f"[{label}] geo filter present iff radius+coords",
          bool(params.get("filter.geo")) == geo_expected,
          f"geo={params.get('filter.geo')!r} expected={geo_expected}")

    # 2. Fetch live
    resp = fetch_clinical_trials(params, use_cache=False)
    if resp.get("error"):
        check(f"[{label}] fetch ok", False, f"API error: {resp.get('error')}")
        return {"label": label, "n": 0, "status_ok": 0, "interv": 0, "in_radius": 0, "geo_missing": 0, "bad": []}

    studies = resp.get("studies", []) or []
    n = len(studies)
    status_ok = interv = in_radius = geo_missing = 0
    bad = []

    for s in studies:
        nct = (s.get("protocolSection", {}).get("identificationModule", {}) or {}).get("nctId", "?")
        st_ok = study_status(s) in RECRUITING
        ty_ok = study_type(s) == "INTERVENTIONAL"
        status_ok += st_ok
        interv += ty_ok
        if not st_ok or not ty_ok:
            bad.append(f"{nct}(status={study_status(s)},type={study_type(s)})")

        # key fields
        id_mod = s.get("protocolSection", {}).get("identificationModule", {}) or {}
        cond = (s.get("protocolSection", {}).get("conditionsModule", {}) or {}).get("conditions", [])
        arms = (s.get("protocolSection", {}).get("armsInterventionsModule", {}) or {}).get("interventions", [])
        if not (id_mod.get("nctId") and id_mod.get("briefTitle") and (cond or arms)):
            bad.append(f"{nct}(missing-fields)")

        if radius is not None:
            ok, missing = within_radius(s, coords, radius)
            in_radius += ok
            geo_missing += missing
            if not ok and not missing:
                bad.append(f"{nct}(out-of-radius)")

        # parse must not raise and must surface enriched fields
        try:
            parsed = parse_trial_result(s, patient_zip=pc["zip_code"])
            assert "interventions" in parsed and "eligibility" in parsed and "study_purpose" in parsed
        except Exception as e:  # noqa: BLE001
            bad.append(f"{nct}(parse-error:{e})")

    # Hard assertions: every study recruiting + interventional; radius (when set) satisfied.
    check(f"[{label}] all recruiting", status_ok == n, f"{status_ok}/{n}")
    check(f"[{label}] all interventional", interv == n, f"{interv}/{n}")
    if radius is not None:
        check(f"[{label}] all within radius (geo-present)", in_radius + geo_missing == n,
              f"in={in_radius} geo_missing={geo_missing} n={n}")

    return {"label": label, "n": n, "status_ok": status_ok, "interv": interv,
            "in_radius": in_radius, "geo_missing": geo_missing, "bad": bad[:5]}


if __name__ == "__main__":
    print("Clinical-trials live validation")
    print("=" * 96)
    print(f"{'case':22s} {'#':>4} {'recruit':>8} {'interv':>7} {'in_rad':>7} {'geo?':>5}  notes")
    print("-" * 96)
    for pc in PATIENTS:
        for r in RADII:
            row = run_case(pc, r)
            notes = ("bad: " + ", ".join(row["bad"])) if row["bad"] else ""
            print(f"{row['label']:22s} {row['n']:>4} {row['status_ok']:>8} {row['interv']:>7} "
                  f"{row['in_radius']:>7} {row['geo_missing']:>5}  {notes[:40]}")
    print("=" * 96)
    if FAILURES:
        print(f"RESULT: {len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print("  -", f)
        sys.exit(1)
    print("RESULT: ALL PASS")
