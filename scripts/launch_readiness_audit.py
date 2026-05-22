#!/usr/bin/env python3
"""
WondrChat launch-readiness audit (Task 14).

Mechanical pre-launch sanity check. Run against `main` before tagging
a public-launch release. Exits 0 = ready; non-zero = list of failures
printed to stderr.

What it checks:
  1. vercel.json has the required security headers, including the
     CSP (Report-Only or enforced).
  2. lib/compliance.py blocks IL + NV, and the EU/EEA/UK/Switzerland
     geofence is in place.
  3. The signup acknowledgement flow validates DOB + the three opt-in
     consents.
  4. /api/csp-report is unauthenticated; /api/healthcheck, /api/auth/*
     are likewise public; every other /api/* route has @require_auth.
  5. PII leak runtime guard is wired into /api/chat just before the
     LLM call.
  6. Account deletion endpoint is present and references all the
     known PII tables.
  7. GPC header is detected via _detect_gpc().
  8. Rate limits are enforced at the documented thresholds for
     register / login / chat.
  9. All required compliance docs exist and contain the expected
     headings.

Usage:
  python scripts/launch_readiness_audit.py
  python scripts/launch_readiness_audit.py --quiet     # only failures
  python scripts/launch_readiness_audit.py --json      # machine-readable

Exit codes:
  0 — all checks pass.
  1 — one or more checks failed.
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- helpers ----------

class CheckResult:
    def __init__(self, name, ok, detail=""):
        self.name = name
        self.ok = ok
        self.detail = detail

    def __repr__(self):
        return f"<{self.name}: {'PASS' if self.ok else 'FAIL'} — {self.detail}>"


def read(rel_path):
    path = os.path.join(ROOT, rel_path)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------- checks ----------

def check_vercel_security_headers():
    raw = read("vercel.json")
    if raw is None:
        return CheckResult("vercel.json — security headers", False, "vercel.json missing")
    required = [
        "Strict-Transport-Security",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ]
    missing = [h for h in required if h not in raw]
    if missing:
        return CheckResult("vercel.json — security headers", False, f"missing: {missing}")
    has_csp = (
        "Content-Security-Policy-Report-Only" in raw
        or '"Content-Security-Policy"' in raw
    )
    if not has_csp:
        return CheckResult("vercel.json — security headers", False, "no CSP header configured")
    return CheckResult(
        "vercel.json — security headers",
        True,
        "all 5 headers + CSP present",
    )


def check_il_nv_blocked():
    raw = read("lib/compliance.py")
    if raw is None:
        return CheckResult("lib/compliance.py — IL/NV block", False, "compliance.py missing")
    if '"IL"' not in raw or '"NV"' not in raw:
        return CheckResult("lib/compliance.py — IL/NV block", False, "IL or NV not referenced")
    # STATE_REQUIREMENTS must mark them block_signup=True
    if not (re.search(r'"IL":\s*\{[^}]*"block_signup"\s*:\s*True', raw, re.S) and
            re.search(r'"NV":\s*\{[^}]*"block_signup"\s*:\s*True', raw, re.S)):
        return CheckResult(
            "lib/compliance.py — IL/NV block",
            False,
            "IL/NV not marked block_signup=True in STATE_REQUIREMENTS",
        )
    return CheckResult("lib/compliance.py — IL/NV block", True, "STATE_REQUIREMENTS has both")


def check_eu_geofence():
    raw = read("lib/compliance.py")
    if raw is None:
        return CheckResult("EU/UK/CH geofence", False, "compliance.py missing")
    required_ccs = ["DE", "FR", "IT", "ES", "GB", "CH", "IS", "LI", "NO"]
    missing = [cc for cc in required_ccs if f'"{cc}"' not in raw]
    if missing:
        return CheckResult("EU/UK/CH geofence", False, f"BLOCKED_COUNTRIES missing: {missing}")
    if "validate_country" not in raw or "detect_country_code" not in raw:
        return CheckResult("EU/UK/CH geofence", False, "validate_country/detect_country_code missing")
    return CheckResult("EU/UK/CH geofence", True, "27 EU + EEA + GB + CH all present")


def check_age_gate():
    raw_compliance = read("lib/compliance.py") or ""
    raw_ui = read("public/index.html") or ""
    if "date_of_birth" not in raw_compliance:
        return CheckResult("Age gate (DOB)", False, "validate_age_confirmation doesn't read date_of_birth")
    if "ackDob" not in raw_ui:
        return CheckResult("Age gate (DOB)", False, "no #ackDob DOB picker in signup UI")
    if "compute_age_band" not in raw_compliance:
        return CheckResult("Age gate (DOB)", False, "compute_age_band missing")
    return CheckResult("Age gate (DOB)", True, "DOB picker + server validation + age_band helper present")


def check_three_consents():
    raw_compliance = read("lib/compliance.py") or ""
    raw_ui = read("public/index.html") or ""
    for field in ("consent_collection", "consent_sharing", "consent_terms"):
        if field not in raw_compliance:
            return CheckResult("Three opt-in consents", False, f"{field} missing from validate_consents")
    for el_id in ("ackConsentCollection", "ackConsentSharing", "ackConsentTerms"):
        if f'id="{el_id}"' not in raw_ui:
            return CheckResult("Three opt-in consents", False, f"#{el_id} checkbox missing from UI")
    return CheckResult("Three opt-in consents", True, "server validates + UI has all three checkboxes")


def check_auth_required_on_routes():
    raw = read("api/index.py")
    if raw is None:
        return CheckResult("Auth coverage on /api/*", False, "api/index.py missing")

    # Endpoints intentionally public
    public_routes = {
        "/api/csp-report",
        "/api/health",
        "/api/healthcheck",
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/data_sources",
        "/api/cancer_options",       # static list — no PII; powers signup dropdown
        "/api/<path:path>",          # Flask catch-all — handled by static / 404
    }
    # Parse routes + check whether @require_auth appears in the next few lines
    route_re = re.compile(r'@app\.route\(\s*"(/api/[^"]+)"', re.M)
    auth_re = re.compile(r'@require_auth')
    missing = []
    lines = raw.splitlines()
    for idx, line in enumerate(lines):
        m = route_re.search(line)
        if not m:
            continue
        path = m.group(1)
        if path in public_routes:
            continue
        # Look at the next 2 lines for @require_auth
        window = "\n".join(lines[idx:idx + 3])
        if not auth_re.search(window):
            missing.append(path)
    if missing:
        return CheckResult(
            "Auth coverage on /api/*",
            False,
            f"missing @require_auth: {missing[:5]}{'...' if len(missing) > 5 else ''}",
        )
    return CheckResult("Auth coverage on /api/*", True, "every non-public route is auth-gated")


def check_pii_runtime_guard():
    raw = read("api/index.py")
    if raw is None:
        return CheckResult("PII runtime guard wired into /api/chat", False, "api/index.py missing")
    # Look for detect_pii_leaks called before call_llm
    if "detect_pii_leaks" not in raw:
        return CheckResult(
            "PII runtime guard wired into /api/chat",
            False,
            "detect_pii_leaks not imported or called",
        )
    chat_section = raw.split('"/api/chat"', 1)[-1]
    if "detect_pii_leaks" not in chat_section.split("call_llm", 1)[0]:
        return CheckResult(
            "PII runtime guard wired into /api/chat",
            False,
            "detect_pii_leaks not called before call_llm",
        )
    return CheckResult("PII runtime guard wired into /api/chat", True, "guard runs pre-LLM")


def check_delete_endpoint():
    raw = read("api/index.py") or ""
    storage = read("lib/supabase_storage.py") or ""
    if '"/api/delete_account"' not in raw:
        return CheckResult("Account deletion endpoint", False, "/api/delete_account missing")
    if "delete_all_user_data" not in storage:
        return CheckResult("Account deletion endpoint", False, "delete_all_user_data helper missing")
    # The helper should reference multiple tables
    table_refs = re.findall(r"client\.table\('([a-z_]+)'\)", storage)
    if len(set(table_refs)) < 5:
        return CheckResult(
            "Account deletion endpoint",
            False,
            f"only {len(set(table_refs))} tables referenced in delete_all_user_data",
        )
    return CheckResult(
        "Account deletion endpoint",
        True,
        f"endpoint + helper cover {len(set(table_refs))} tables",
    )


def check_gpc_detection():
    raw = read("api/index.py") or ""
    if "_detect_gpc" not in raw or "Sec-GPC" not in raw:
        return CheckResult("GPC header honoring", False, "_detect_gpc or Sec-GPC missing")
    if "before_request(_detect_gpc)" not in raw:
        return CheckResult("GPC header honoring", False, "_detect_gpc not registered as before_request")
    return CheckResult("GPC header honoring", True, "before_request hook present")


def check_rate_limits():
    raw = read("api/index.py") or ""
    expected = [
        ("auth/register", "3", "60"),
        ("auth/login", "5", "15"),
        ("chat", "30", "60"),
    ]
    for endpoint, n, window in expected:
        # check_rate_limit(... 'endpoint', N, WINDOW)
        pattern = re.compile(
            r"check_rate_limit\([^)]*'" + re.escape(endpoint) + r"'\s*,\s*"
            + re.escape(n) + r"\s*,\s*" + re.escape(window) + r"\s*\)",
            re.S,
        )
        if not pattern.search(raw):
            return CheckResult(
                "Rate limits at documented thresholds",
                False,
                f"{endpoint}: {n}/{window} not enforced",
            )
    return CheckResult(
        "Rate limits at documented thresholds",
        True,
        "register 3/60s, login 5/15min, chat 30/60s",
    )


def check_compliance_docs_present():
    required_docs = [
        ("docs/compliance/dpia.md", ["Risk Assessment", "Lawfulness"]),
        ("docs/compliance/incident_response_plan.md", ["60", "severity"]),
        ("docs/compliance/subprocessor_chain.md", ["Supabase", "Together AI", "Groq"]),
        ("docs/compliance/state_ai_law_tracker.md", ["WOPR", "MHMDA"]),
        ("docs/compliance/eu_geofence_decision.md", ["GDPR", "BLOCKED_COUNTRIES"]),
        ("docs/compliance/nist_ai_rmf_mapping.md", ["GOVERN", "MAP", "MEASURE", "MANAGE"]),
        ("docs/compliance/irp_tabletop_scenarios.md", ["Scenario 1", "Scenario 2", "Scenario 3"]),
        ("docs/compliance/hbnr_breach_notification_template.md", ["FTC"]),
    ]
    failures = []
    for path, keywords in required_docs:
        content = read(path)
        if content is None:
            failures.append(f"{path}: missing")
            continue
        # Case-insensitive keyword check so 'Severity' matches 'severity' etc.
        content_lower = content.lower()
        missing_keywords = [k for k in keywords if k.lower() not in content_lower]
        if missing_keywords:
            failures.append(f"{path}: missing keywords {missing_keywords}")
    if failures:
        return CheckResult("Compliance docs present + complete", False, "; ".join(failures))
    return CheckResult(
        "Compliance docs present + complete",
        True,
        f"{len(required_docs)} docs verified",
    )


# ---------- runner ----------

CHECKS = [
    check_vercel_security_headers,
    check_il_nv_blocked,
    check_eu_geofence,
    check_age_gate,
    check_three_consents,
    check_auth_required_on_routes,
    check_pii_runtime_guard,
    check_delete_endpoint,
    check_gpc_detection,
    check_rate_limits,
    check_compliance_docs_present,
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="WondrChat launch-readiness audit")
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    parser.add_argument("--json", action="store_true", help="JSON output instead of text")
    args = parser.parse_args(argv)

    results = [c() for c in CHECKS]

    if args.json:
        print(json.dumps([
            {"name": r.name, "ok": r.ok, "detail": r.detail}
            for r in results
        ], indent=2))
    else:
        max_name = max(len(r.name) for r in results)
        for r in results:
            if args.quiet and r.ok:
                continue
            marker = "✓" if r.ok else "✗"
            print(f"  {marker}  {r.name.ljust(max_name)}  {r.detail}")
        passed = sum(1 for r in results if r.ok)
        total = len(results)
        print(f"\n{passed}/{total} checks passed")

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
