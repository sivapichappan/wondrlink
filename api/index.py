# api/index.py - WondrLink Flask API for Vercel Serverless
import os
import sys
import json
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify

# Add lib to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from dotenv import load_dotenv
load_dotenv()

# Import lib modules
from supabase_client import get_supabase_client, verify_token
from auth_helpers import register_user, login_user, logout_user, get_current_user
from supabase_storage import (
    save_profile, load_profile, clear_profile,
    load_all_chunks, get_conversation_history, add_conversation,
    get_document_metadata, update_profile_with_sources,
    check_acknowledgement, save_acknowledgement,
    save_chat_message, load_chat_history, clear_chat_history,
    record_consent_action, get_consent_status, VALID_CONSENT_KEYS,
    create_conversation, list_conversations, get_conversation_messages,
    get_conversation_history_by_id, append_qa_to_conversation,
    rename_conversation, delete_conversation, search_conversations,
    conversation_belongs_to_user, get_or_create_conversation,
)
from profile_utils import (
    extract_patient_context_complex, format_patient_summary_complex,
    set_profile, get_profile, parse_profile_json
)
from pdf_utils import search_chunks, hybrid_search
from llm_utils import (
    assemble_prompt, call_llm, classify_query_type,
    trim_incomplete_sentence, validate_response, enhanced_medical_validation,
    format_conversation_context, get_llm_status, sanitize_query,
    extract_profile_updates_from_query, get_relevant_resources,
    postprocess_citations
)
from clinical_trials import (
    search_trials_for_patient, format_trials_for_chat, is_clinical_trial_query,
    validate_trial_search_readiness, count_trials_for_radii
)

# -------------------------
# Config & Globals
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wondr-api")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5000").split(",")

# -------------------------
# Rate limits — (max_requests, window_seconds) per identity key
# -------------------------
RATE_LIMIT_AUTH_REGISTER = (3, 60)
RATE_LIMIT_AUTH_LOGIN    = (5, 15)
RATE_LIMIT_CHAT          = (30, 60)
RATE_LIMIT_PREVISIT      = (10, 60)
RATE_LIMIT_VISIT_RECAP   = (10, 60)
RATE_LIMIT_APPEAL        = (5, 60)      # insurance appeal
RATE_LIMIT_DEEP_RESEARCH = (3, 300)
RATE_LIMIT_PRIVACY_APPEAL = (3, 86400)  # 3 per day
RATE_LIMIT_MODELER       = (6, 60)      # abuse guard; the real gate is the debounce
RATE_LIMIT_TRIALS_FEEDBACK = (60, 60)   # save/remove/view pings while browsing


def feature_enabled(flag_name: str) -> bool:
    """Per-feature kill switch via env var FEATURE_<NAME>. Defaults to True."""
    return os.getenv(f"FEATURE_{flag_name.upper()}", "true").lower() == "true"


def _resolve_cancer_slug(user_id, profile):
    """Best-effort cancer slug for trial/condition lookups.

    Prefers the profile-derived value (derive_universal_core); falls back to the
    user's persisted selection (get_cancer_slug). Returns None if neither is
    available — callers then use the legacy 'colorectal' default.
    """
    slug = None
    try:
        from profile_validator import derive_universal_core
        slug = (derive_universal_core(profile or {}) or {}).get('cancer_slug')
    except Exception:
        slug = None
    if not slug and user_id:
        try:
            from supabase_storage import get_cancer_slug
            slug = get_cancer_slug(user_id)
        except Exception:
            slug = None
    return slug


def _emit_trials_shown(user_id, surface, results, session_id=None):
    """Trial-search telemetry (Push 3): one compact patient_event per serve.
    Unconditional — telemetry doesn't depend on the modeler flag; excluded
    from the Modeler's timeline via _EXCLUDED_EVENT_KINDS. Never raises."""
    try:
        from supabase_storage import append_patient_event
        trials = results.get("trials") or []
        entries = []
        graph_applied = False
        for t in trials[:12]:
            entry = {"nct_id": t.get("nct_id"),
                     "score": t.get("relevance_score"),
                     "band": (t.get("relevance") or {}).get("band")}
            graph = (t.get("relevance") or {}).get("graph") or {}
            if graph.get("applied"):
                graph_applied = True
                if graph.get("delta"):
                    entry["graph_delta"] = graph["delta"]
            entries.append(entry)
        append_patient_event(user_id, "trials_shown", payload={
            "surface": surface,
            "count": len(trials),
            "total_found": results.get("total_found", 0),
            "radius_miles": results.get("radius_miles"),
            "relaxed_location": results.get("relaxed_location", False),
            "graph_applied": graph_applied,
            "trials": entries,
        }, source="system", session_id=session_id)
    except Exception:
        logger.warning("trials_shown emit failed (non-fatal)")


# Will be assigned after `app` is created (see below).
def _detect_gpc():
    """Detect the Global Privacy Control opt-out signal (Sec-GPC: 1).
       Honored per CCPA, Colorado, Connecticut, and Oregon laws."""
    try:
        request.gpc_opted_out = request.headers.get("Sec-GPC", "").strip() == "1"
    except Exception:
        request.gpc_opted_out = False

def _origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    origin = origin.strip().lower()
    allowed = [o.strip().lower() for o in ALLOWED_ORIGINS if o]
    if "*" in allowed:
        return True
    return origin in allowed

# Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "wondrlink-dev-secret-key")
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB — allows PDF uploads on /api/insurance_appeal

# Register the Global Privacy Control detection hook. Sets request.gpc_opted_out
# (bool) for downstream endpoints that store optional/non-essential data.
app.before_request(_detect_gpc)

# -------------------------
# Auth Decorator
# -------------------------
def require_auth(f):
    """Decorator to require JWT authentication via Authorization header."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization required", "code": "AUTH_REQUIRED"}), 401

        token = auth_header.split(' ')[1]
        user = verify_token(token)

        if not user:
            return jsonify({"error": "Invalid or expired token", "code": "INVALID_TOKEN"}), 401

        # Attach user to request context
        request.user = user
        return f(*args, **kwargs)
    return decorated_function

# -------------------------
# CSP Report Endpoint
# -------------------------
# Browsers POST CSP violation reports here when the report-only header detects
# a blocked resource. We log counts + the violated directive + the blocked URI
# (no PII — the URI is either a CDN or a third-party origin). Used during the
# CSP rollout window to discover legitimate violations before flipping the
# header from Report-Only to enforced.
@app.route("/api/csp-report", methods=["POST"])
def api_csp_report():
    try:
        # Browsers send application/csp-report or application/json. Try both.
        raw = request.get_data(as_text=True) or ""
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        report = data.get("csp-report") or data or {}
        # Only log a small, non-PII surface
        directive = report.get("violated-directive") or report.get("effective-directive") or "unknown"
        blocked_uri = (report.get("blocked-uri") or "")[:200]
        document_uri = (report.get("document-uri") or "")[:200]
        logger.info(
            "CSP-VIOLATION directive=%s blocked=%s on=%s",
            directive, blocked_uri, document_uri
        )
        # Always 204 — browsers ignore the response body
        return ("", 204)
    except Exception:
        logger.exception("CSP report handler error")
        return ("", 204)


# -------------------------
# Auth Routes
# -------------------------
@app.route("/api/auth/register", methods=["POST"])
def api_register():
    """Register a new user with Supabase Auth."""
    try:
        # EU/EEA/UK/Swiss geofence — we don't currently serve these regions
        # because we lack the GDPR / EU AI Act compliance build.
        try:
            from compliance import validate_country
            ok, msg, code = validate_country(request.headers)
            if not ok:
                return jsonify({"error": msg, "code": "REGION_BLOCKED"}), code
        except Exception:
            # If validation crashes, fail open — the state + consent gates
            # are still authoritative downstream and we'd rather not block
            # all signups on an upstream regression.
            pass

        # Rate limit registration by IP
        from rate_limit import check_rate_limit
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        allowed, remaining = check_rate_limit(client_ip, 'auth/register', *RATE_LIMIT_AUTH_REGISTER)
        if not allowed:
            return jsonify({"error": "Too many registration attempts. Please try again later."}), 429

        # Try to get JSON data from request body
        data = {}
        try:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                data = json.loads(raw_data)
            elif request.is_json:
                data = request.get_json(silent=True) or {}
        except Exception:
            data = {}

        email = data.get("email", "").strip()
        password = data.get("password", "")

        user_data, error = register_user(email, password)

        if error:
            return jsonify({"error": error}), 400

        logger.info(f"New user registered: user_id={user_data.get('user_id')}")
        return jsonify({
            "status": "ok",
            "message": "Account created successfully",
            "user": {
                "user_id": user_data["user_id"],
                "email": user_data["email"]
            },
            "access_token": user_data.get("access_token"),
            "refresh_token": user_data.get("refresh_token")
        })
    except Exception as e:
        logger.exception("Registration error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """Authenticate and log in a user."""
    try:
        # Rate limit login by IP
        from rate_limit import check_rate_limit
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        allowed, remaining = check_rate_limit(client_ip, 'auth/login', *RATE_LIMIT_AUTH_LOGIN)
        if not allowed:
            return jsonify({"error": "Too many login attempts. Please try again in 15 minutes."}), 429

        # Try to get JSON data from request body
        data = {}
        try:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                data = json.loads(raw_data)
            elif request.is_json:
                data = request.get_json(silent=True) or {}
        except Exception:
            data = {}

        email = data.get("email", "").strip()
        password = data.get("password", "")

        user_data, error = login_user(email, password)

        if error:
            return jsonify({"error": error}), 401

        logger.info(f"User logged in: user_id={user_data.get('user_id')}")
        return jsonify({
            "status": "ok",
            "message": "Logged in successfully",
            "user": {
                "user_id": user_data["user_id"],
                "email": user_data["email"]
            },
            "access_token": user_data["access_token"],
            "refresh_token": user_data["refresh_token"]
        })
    except Exception as e:
        logger.exception("Login error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/auth/phone/send", methods=["POST"])
def api_phone_send():
    """Sage phone sign-in step 1: text a one-time code to the number.
    First-time numbers are created automatically at verify time."""
    try:
        # Same geofence as registration (a first-time phone number IS a signup).
        try:
            from compliance import validate_country
            ok, msg, code = validate_country(request.headers)
            if not ok:
                return jsonify({"error": msg, "code": "REGION_BLOCKED"}), code
        except Exception:
            pass

        from rate_limit import check_rate_limit
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        allowed, _rem = check_rate_limit(client_ip, 'auth/phone_send', *RATE_LIMIT_AUTH_LOGIN)
        if not allowed:
            return jsonify({"error": "Too many codes requested. Please wait and try again."}), 429

        data = request.get_json(silent=True) or {}
        from auth_helpers import send_phone_otp
        ok, error = send_phone_otp(str(data.get("phone", "")))
        if not ok:
            return jsonify({"error": error}), 400
        return jsonify({"status": "ok", "message": "Code sent"})
    except Exception:
        logger.exception("Phone OTP send error")
        return jsonify({"error": "Could not send a code. Please try again."}), 500


@app.route("/api/auth/phone/verify", methods=["POST"])
def api_phone_verify():
    """Sage phone sign-in step 2: verify the code, return a session
    (same token shape as /api/auth/login so the client plumbing is shared)."""
    try:
        from rate_limit import check_rate_limit
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        allowed, _rem = check_rate_limit(client_ip, 'auth/phone_verify', *RATE_LIMIT_AUTH_LOGIN)
        if not allowed:
            return jsonify({"error": "Too many attempts. Please wait and try again."}), 429

        data = request.get_json(silent=True) or {}
        from auth_helpers import verify_phone_otp
        user_data, error = verify_phone_otp(str(data.get("phone", "")),
                                            str(data.get("code", "")))
        if error:
            return jsonify({"error": error}), 401
        logger.info(f"Phone user logged in: user_id={user_data.get('user_id')}")
        return jsonify({
            "status": "ok",
            "message": "Logged in successfully",
            "user": {
                "user_id": user_data["user_id"],
                "email": user_data.get("email"),
                "phone": user_data.get("phone"),
            },
            "access_token": user_data["access_token"],
            "refresh_token": user_data["refresh_token"],
        })
    except Exception:
        logger.exception("Phone OTP verify error")
        return jsonify({"error": "Sign-in failed. Please try again."}), 500


@app.route("/api/account/basics", methods=["POST"])
@require_auth
def api_account_basics():
    """
    Sage onboarding basics (screens 2/2a/2b): who the account is for + the
    minimal patient facts. Merges into raw_profile.patient (never replaces)
    and absorbs the facts as confirmed form-sourced beliefs.
    """
    try:
        user_id = request.user["user_id"]
        data = request.get_json(silent=True) or {}

        perspective = str(data.get("perspective", "self")).lower()
        if perspective not in ("self", "caregiver"):
            return jsonify({"error": "perspective must be self or caregiver"}), 400
        account_holder_name = str(data.get("account_holder_name", "")).strip()[:80]
        if not account_holder_name:
            return jsonify({"error": "Please tell us your name"}), 400
        relationship = (str(data.get("relationship", "")).strip()[:40] or None) \
            if perspective == "caregiver" else None
        patient_name = str(data.get("patient_name", "")).strip()[:80] or \
            (account_holder_name if perspective == "self" else "")
        if perspective == "caregiver" and not patient_name:
            return jsonify({"error": "Please tell us their name"}), 400

        patient_updates: dict = {"firstName": patient_name}
        birth_year = data.get("birth_year")
        try:
            birth_year = int(birth_year)
            from datetime import datetime as _dt
            age = _dt.utcnow().year - birth_year
            if 0 < age < 120:
                patient_updates["age"] = age
        except (TypeError, ValueError):
            pass
        gender = str(data.get("gender", "")).strip()
        if gender in ("Female", "Male", "Other"):
            patient_updates["sex"] = gender
        location = data.get("location")
        if isinstance(location, dict) and (location.get("display") or location.get("lat")):
            patient_updates["location"] = {
                "lat": location.get("lat"), "lng": location.get("lng"),
                "display": str(location.get("display", ""))[:80],
            }
            # Trials still key on ZIP today: keep it in sync when the free-text
            # location is a US ZIP code.
            display = str(location.get("display", "")).strip()
            if display.isdigit() and len(display) == 5:
                patient_updates["zipCode"] = display

        from supabase_storage import save_account_basics
        if not save_account_basics(user_id, perspective, account_holder_name,
                                   patient_updates, relationship):
            return jsonify({"error": "Could not save. Please try again."}), 500

        # Absorb the basics as confirmed form-sourced beliefs (best effort).
        try:
            from patient_model import absorb_form_profile
            profile = load_profile(user_id)
            if profile:
                absorb_form_profile(profile, only_missing=True)
                save_profile(user_id, profile)
        except Exception:
            logger.exception("basics belief absorption failed (non-fatal)")

        return jsonify({"status": "ok"})
    except Exception:
        logger.exception("account basics error")
        return jsonify({"error": "Could not save. Please try again."}), 500


@app.route("/api/auth/logout", methods=["POST"])
@require_auth
def api_logout():
    """Log out the current user."""
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(' ')[1] if auth_header and auth_header.startswith('Bearer ') else None

    if token:
        logout_user(token)

    logger.info("User logged out")
    return jsonify({"status": "ok", "message": "Logged out successfully"})


@app.route("/api/auth/me", methods=["GET"])
def api_get_current_user():
    """Get current logged-in user info."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"authenticated": False}), 200

    token = auth_header.split(' ')[1]
    user = get_current_user(token)

    if not user:
        return jsonify({"authenticated": False}), 200

    return jsonify({
        "authenticated": True,
        "user": user
    })

# -------------------------
# Profile Routes
# -------------------------
@app.route("/api/upload_profile", methods=["POST"])
@require_auth
def api_upload_profile():
    """Upload a patient profile JSON."""
    try:
        user_id = request.user["user_id"]

        # Handle JSON body
        if request.is_json:
            profile = request.get_json(silent=True)
            if not profile:
                return jsonify({"error": "Invalid JSON body"}), 400
        else:
            # Handle file upload
            file = request.files.get("file")
            if not file:
                return jsonify({"error": "No file or JSON provided"}), 400

            content = file.read()
            profile = json.loads(content.decode('utf-8'))

        # A form/wizard upload replaces the profile document — carry over the
        # app-state sub-objects it doesn't know about (beliefs, model_state,
        # visit recaps, …) and absorb the form's fields into the belief store
        # as source=form / confirmed (the form stays a first-class accelerator).
        try:
            from patient_model import absorb_form_profile, carry_over_app_state
            profile = carry_over_app_state(profile, load_profile(user_id))
            absorb_form_profile(profile)
        except Exception:
            logger.exception("Form belief absorption failed (profile still saved)")

        # Save to Supabase
        if not save_profile(user_id, profile):
            logger.error(f"Failed to save profile to database for user {user_id}")
            return jsonify({"error": "Failed to save profile to database. Please check server logs."}), 500

        # Set in memory for this request
        set_profile(profile)

        # Extract context
        patient_context = extract_patient_context_complex(profile)
        patient_summary = format_patient_summary_complex(patient_context)

        logger.info(f"Loaded patient profile for user {user_id}")
        return jsonify({
            "status": "ok",
            "profile": profile,
            "patient_summary": patient_summary,
            "context": patient_context
        })
    except Exception as e:
        logger.exception("upload_profile error")
        return jsonify({"error": str(e)}), 400


@app.route("/api/confirm_belief", methods=["POST"])
@require_auth
def api_confirm_belief():
    """
    Resolve a pending belief confirmation (the "is that right?" chip).

    Body: {"confirmation_id": str, "accept": bool}
    accept=true  -> the fact is committed as confirmed.
    accept=false -> the fact is dropped; response carries a gentle
                    corrected_question the client can prefill.
    """
    try:
        user_id = request.user["user_id"]
        data = request.get_json(silent=True) or {}
        confirmation_id = data.get("confirmation_id")
        accept = data.get("accept")
        if not confirmation_id or not isinstance(accept, bool):
            return jsonify({"error": "confirmation_id and accept (boolean) are required"}), 400

        from patient_model import confirm_belief
        result = confirm_belief(user_id, str(confirmation_id), accept)
        if result.get("status") == "not_found":
            return jsonify({"error": "Confirmation not found (it may have expired)"}), 404
        if result.get("status") == "error":
            return jsonify({"error": "Failed to save"}), 500
        return jsonify(result)
    except Exception as e:
        logger.exception("confirm_belief error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/modeler/run", methods=["POST"])
@require_auth
def api_modeler_run():
    """
    End-of-conversation trigger (client fire-and-forget): run one Modeler pass
    for the caller. Debounce gates inside run_for_user do the real limiting;
    the rate limit here is only an abuse guard. 403 while FEATURE_MODELER is off.
    """
    try:
        user_id = request.user["user_id"]
        from rate_limit import check_rate_limit
        allowed, _remaining = check_rate_limit(user_id, 'modeler_run', *RATE_LIMIT_MODELER)
        if not allowed:
            return jsonify({"error": "Too many requests"}), 429

        from modeler import modeler_enabled, run_for_user
        if not modeler_enabled():
            return jsonify({"error": "disabled"}), 403
        result = run_for_user(user_id, trigger="client")
        status_code = 500 if result.get("status") == "error" else 200
        return jsonify(result), status_code
    except Exception:
        logger.exception("modeler run error")
        return jsonify({"status": "error"}), 500


@app.route("/api/modeler/cron", methods=["GET"])
def api_modeler_cron():
    """
    Nightly catch-up (Vercel cron). Auth: Vercel sends Authorization: Bearer
    $CRON_SECRET when that env var exists. Time-guarded loop, oldest-run-first;
    the response carries counts only — never user ids.
    """
    import hmac as _hmac
    secret = os.environ.get("CRON_SECRET", "")
    provided = request.headers.get("Authorization", "")
    if not secret or not _hmac.compare_digest(provided, f"Bearer {secret}"):
        return jsonify({"error": "unauthorized"}), 401

    from modeler import modeler_enabled, run_for_user
    if not modeler_enabled():
        return jsonify({"status": "disabled"})

    import time as _time
    started = _time.time()
    from supabase_storage import load_profile, recent_event_user_ids
    candidates = recent_event_user_ids(hours=26)

    # Oldest last-run first so a backlog drains fairly across nights.
    def _last_run(uid: str) -> str:
        profile = load_profile(uid) or {}
        return ((profile.get("connections") or {}).get("meta") or {}).get("last_run_at") or ""
    candidates.sort(key=_last_run)

    ran = skipped = errors = 0
    for uid in candidates:
        if _time.time() - started > 40:   # leave headroom under maxDuration 60
            break
        result = run_for_user(uid, trigger="cron")
        status = result.get("status")
        if status == "ran":
            ran += 1
        elif status == "error":
            errors += 1
        else:
            skipped += 1
    return jsonify({"candidates": len(candidates), "ran": ran, "skipped": skipped,
                    "errors": errors, "elapsed_ms": int((_time.time() - started) * 1000)})


@app.route("/api/trials/feedback", methods=["POST"])
@require_auth
def api_trials_feedback():
    """Trial-interaction telemetry (Push 3): saved / removed / viewed.
    The client watchlist stays client-side — this event is the server-side
    record, and it feeds the Modeler's timeline (genuine longitudinal signal)."""
    try:
        user_id = request.user["user_id"]
        from rate_limit import check_rate_limit
        allowed, _remaining = check_rate_limit(user_id, 'trials_feedback',
                                               *RATE_LIMIT_TRIALS_FEEDBACK)
        if not allowed:
            return jsonify({"error": "Too many requests"}), 429

        from clinical_trials import validate_trial_feedback
        payload = validate_trial_feedback(request.get_json(silent=True))
        if payload is None:
            return jsonify({"error": "Invalid feedback payload"}), 400

        from supabase_storage import append_patient_event
        append_patient_event(user_id, "trial_feedback", payload=payload,
                             source="client")
        return jsonify({"status": "ok"})
    except Exception:
        logger.exception("trials feedback error")
        return jsonify({"status": "error"}), 500


@app.route("/api/safety/log_symptom", methods=["POST"])
@require_auth
def api_safety_log_symptom():
    """T2 escalation card's "Log this symptom" action: one timestamped
    patient_events row so the symptom is on the record when the patient
    talks to their care team (supervisor doc: "the one useful non-medical
    action"). No free-text is required; the note is patient-authored."""
    try:
        user_id = request.user["user_id"]
        from rate_limit import check_rate_limit
        allowed, _remaining = check_rate_limit(user_id, 'safety_log_symptom',
                                               *RATE_LIMIT_TRIALS_FEEDBACK)
        if not allowed:
            return jsonify({"error": "Too many requests"}), 429

        body = request.get_json(silent=True) or {}
        tier = str(body.get("tier") or "")
        category = str(body.get("category") or "")[:80]
        note = str(body.get("note") or "")[:500]
        if tier not in ("T1", "T2", "T3", "MH") or not category:
            return jsonify({"error": "Invalid symptom payload"}), 400

        from supabase_storage import append_patient_event
        append_patient_event(
            user_id, "symptom_report",
            payload={"tier": tier, "category": category, "note": note},
            source="safety_card",
        )
        return jsonify({"status": "ok"})
    except Exception:
        logger.exception("safety log_symptom error")
        return jsonify({"status": "error"}), 500


@app.route("/api/modeler/graph", methods=["GET"])
@require_auth
def api_modeler_graph():
    """The caller's own connections graph (review/demo surface; shadow-safe)."""
    try:
        from modeler import ensure_connections, modeler_enabled
        if not modeler_enabled():
            return jsonify({"error": "disabled"}), 403
        user_id = request.user["user_id"]
        profile = load_profile(user_id) or {}
        return jsonify({"connections": ensure_connections(profile)})
    except Exception:
        logger.exception("modeler graph error")
        return jsonify({"error": "Failed to load graph"}), 500


@app.route("/api/get_patient", methods=["GET"])
@require_auth
def api_get_patient():
    """Get the current patient profile."""
    try:
        user_id = request.user["user_id"]

        # Load from Supabase
        profile = load_profile(user_id)

        if profile:
            set_profile(profile)
            patient_context = extract_patient_context_complex(profile)
            patient_summary = format_patient_summary_complex(patient_context)

            # Lifecycle read model: stage + a compact coverage summary
            # ("What WondrChat knows") for the mobile My Care surface.
            lifecycle_stage = "getting_to_know_you"
            coverage_summary = None
            try:
                from question_policy import compute_coverage
                lifecycle_stage = (profile.get("model_state") or {}).get(
                    "lifecycle_stage", "getting_to_know_you")
                cov = compute_coverage(profile, _resolve_cancer_slug(user_id, profile))
                coverage_summary = {
                    "score": cov["score"],
                    "known_count": cov["known_count"],
                    "missing_top": [topic for topic, _w in cov["missing_ranked"][:3]],
                }
            except Exception:
                logger.exception("Coverage summary failed (non-fatal)")

            return jsonify({
                "profile": profile,
                "patient_summary": patient_summary,
                "context": patient_context,
                "lifecycle_stage": lifecycle_stage,
                "coverage": coverage_summary
            })
        else:
            return jsonify({})
    except Exception as e:
        logger.exception("get_patient error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear_profile", methods=["POST"])
@require_auth
def api_clear_profile():
    """Clear the stored patient profile."""
    try:
        user_id = request.user["user_id"]
        clear_profile(user_id)
        set_profile({})
        logger.info(f"Cleared patient profile for user {user_id}")
        return jsonify({"status": "ok", "message": "Profile cleared"})
    except Exception as e:
        logger.exception("clear_profile error")
        return jsonify({"error": str(e)}), 500

# -------------------------
# Acknowledgement Routes
# -------------------------
@app.route("/api/check_acknowledgement", methods=["GET"])
@require_auth
def api_check_acknowledgement():
    """
    Return the user's acknowledgement + consent state. The frontend uses
    this to decide whether to show the extended MHMDA consent modal.

    Response shape:
      {
        "acknowledged": bool,
        "consent_version": str | null,
        "current_version": str,              # what we expect users to be on
        "needs_consent": bool,               # acknowledged && version < current
        "state_restricted": bool,            # IL/NV — user soft-deactivated
      }
    """
    try:
        from compliance import CURRENT_CONSENT_VERSION
        from supabase_storage import get_cancer_slug
        user_id = request.user["user_id"]
        state = check_acknowledgement(user_id)
        acknowledged = state.get('acknowledged', False)
        version = state.get('consent_version')
        # User needs to re-consent if they've never acknowledged, OR if their
        # accepted version is below current.
        needs_consent = (not acknowledged) or (version != CURRENT_CONSENT_VERSION)
        # Multi-cancer: surface the user's selected cancer_slug + display name
        # so the frontend can render the header badge + skip the cancer-picker
        # step on re-login.
        cancer_slug = None
        cancer_display = None
        try:
            cancer_slug = get_cancer_slug(user_id)
            if cancer_slug:
                from cancer_registry import display_name
                cancer_display = display_name(cancer_slug)
        except Exception as _e:
            logger.warning("cancer_slug lookup failed: %s", _e)
        # Sage onboarding: do we still need the who-for + basics screens?
        basics = {}
        try:
            from supabase_storage import get_account_basics
            basics = get_account_basics(user_id)
        except Exception as _e:
            logger.warning("account basics lookup failed: %s", _e)

        return jsonify({
            "acknowledged": acknowledged,
            "consent_version": version,
            "current_version": CURRENT_CONSENT_VERSION,
            "needs_consent": needs_consent,
            "state_restricted": state.get('state_restricted', False),
            "cancer_slug": cancer_slug,
            "cancer_display": cancer_display,
            "needs_cancer_pick": cancer_slug is None,
            "needs_basics": bool(basics.get('needs_basics', False)),
            "perspective": basics.get('perspective', 'self'),
            "account_holder_name": basics.get('account_holder_name'),
        })
    except Exception as e:
        logger.exception("check_acknowledgement error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/save_acknowledgement", methods=["POST"])
@require_auth
def api_save_acknowledgement():
    """
    Save MHMDA-compliant acknowledgement + consents.

    Required body fields:
      - age_confirmed: bool (must be true)
      - state: str (US state code or "non_US"; cannot be in BLOCKED_STATES)
      - consent_collection: bool (must be true)
      - consent_sharing: bool (must be true)
      - consent_terms: bool (must be true)
    """
    if not feature_enabled('strict_compliance'):
        # Legacy single-checkbox flow (back-compat for emergency rollback)
        try:
            user_id = request.user["user_id"]
            success = save_acknowledgement(user_id)
            return jsonify({"status": "ok"} if success else {"error": "save failed"}), (200 if success else 500)
        except Exception as e:
            logger.exception("legacy save_acknowledgement error")
            return jsonify({"error": str(e)}), 500

    try:
        from compliance import (
            validate_consents, validate_age_confirmation, validate_state,
            validate_country,
            build_consent_metadata, CURRENT_CONSENT_VERSION,
        )
        user_id = request.user["user_id"]
        payload = request.get_json(silent=True) or {}

        # EU/EEA/UK/Swiss geofence — catches any signup that made it past
        # auth from a blocked region.
        ok, msg, code = validate_country(request.headers)
        if not ok:
            return jsonify({"error": msg, "code": "REGION_BLOCKED"}), code

        # Age check
        ok, msg = validate_age_confirmation(payload)
        if not ok:
            return jsonify({"error": msg, "field": "age_confirmed"}), 400

        # State check (returns its own status code: 400 for malformed, 422 for blocked)
        ok, msg, code = validate_state(payload.get("state"))
        if not ok:
            return jsonify({"error": msg, "field": "state"}), code

        # Three separate opt-in consents (MHMDA: no bundling)
        ok, msg = validate_consents(payload)
        if not ok:
            return jsonify({"error": msg}), 400

        # Multi-cancer: accept cancer_slug + role from signup picker.
        # Optional at signup time (user can pick later) but recommended.
        cancer_slug = (payload.get("cancer_slug") or "").strip().lower() or None
        role = (payload.get("role") or "patient").strip().lower()
        if cancer_slug:
            try:
                from cancer_registry import exists as _cancer_exists
                if not _cancer_exists(cancer_slug):
                    return jsonify({
                        "error": f"Unknown cancer type: {cancer_slug}",
                        "field": "cancer_slug",
                    }), 400
            except Exception:
                pass

        # Build the audit record and persist
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
        metadata = build_consent_metadata(payload, ip_address=client_ip)
        if cancer_slug:
            metadata['cancer_slug'] = cancer_slug
            metadata['role'] = role
        success = save_acknowledgement(
            user_id,
            consent_metadata=metadata,
            consent_version=CURRENT_CONSENT_VERSION,
        )
        if not success:
            return jsonify({"error": "Failed to save acknowledgement"}), 500

        # Persist cancer_slug + role on patient_profiles (creates a stub row
        # if no full profile exists yet). Best-effort — if this fails we
        # still return success on the consent itself.
        if cancer_slug:
            try:
                from supabase_storage import save_cancer_slug
                save_cancer_slug(user_id, cancer_slug, role)
            except Exception as _e:
                logger.warning("save_cancer_slug after acknowledgement failed: %s", _e)

        return jsonify({
            "status": "ok",
            "message": "Acknowledgement saved",
            "consent_version": CURRENT_CONSENT_VERSION,
            "cancer_slug": cancer_slug,
            "role": role if cancer_slug else None,
        })
    except Exception as e:
        logger.exception("save_acknowledgement error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/consent_status", methods=["GET"])
@require_auth
def api_consent_status():
    """
    Return the user's current consent toggle state — used by the
    Consent Management UI and by chat endpoints to decide whether
    to disable chat.
    """
    try:
        user_id = request.user["user_id"]
        return jsonify(get_consent_status(user_id))
    except Exception as e:
        logger.exception("consent_status error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/withdraw_consent", methods=["POST"])
@require_auth
def api_withdraw_consent():
    """
    Toggle one of the three signup consents off or back on.

    Body:
      - consent_key: 'consent_collection' | 'consent_sharing' | 'consent_terms'
      - action: 'withdraw' | 'restore'
      - reason: optional free-text (<=500 chars)

    MHMDA requires a withdraw-consent affordance separate from
    account deletion. Each toggle is logged immutably; the current
    state per key is the most recent row.
    """
    try:
        user_id = request.user["user_id"]
        payload = request.get_json(silent=True) or {}
        consent_key = (payload.get("consent_key") or "").strip()
        action = (payload.get("action") or "").strip()
        reason = payload.get("reason") or ""

        if consent_key not in VALID_CONSENT_KEYS:
            return jsonify({"error": "Unknown consent_key", "field": "consent_key"}), 400
        if action not in ("withdraw", "restore"):
            return jsonify({"error": "action must be 'withdraw' or 'restore'", "field": "action"}), 400

        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
        try:
            from compliance import _hash_ip, CURRENT_CONSENT_VERSION
        except Exception:
            _hash_ip = lambda x: ""
            CURRENT_CONSENT_VERSION = ""
        ok = record_consent_action(
            user_id=user_id,
            consent_key=consent_key,
            action=action,
            reason=reason,
            consent_version=CURRENT_CONSENT_VERSION,
            ip_hash=_hash_ip(client_ip) if client_ip else "",
        )
        if not ok:
            return jsonify({"error": "Failed to record consent action"}), 500

        return jsonify({"status": "ok", "consent_status": get_consent_status(user_id)})
    except Exception as e:
        logger.exception("withdraw_consent error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/limit_sensitive_pi", methods=["GET", "POST"])
@require_auth
def api_limit_sensitive_pi():
    """
    CCPA / CPRA: surface the "Limit Use of Sensitive Personal Information"
    affordance. We don't use SPI for advertising or sale, so this is
    operationally a no-op; the endpoint records the user's preference
    timestamp so we can produce it on request.

    GET  → returns {limited: bool, confirmed_at: iso8601|None}
    POST → records the preference; idempotent (subsequent posts just refresh
           the timestamp).

    Persistence: a row in the `consent_withdrawals` table with
    consent_key='consent_collection' would conflate flows, so we re-use the
    same table with consent_key='limit_spi' kept loose at runtime — the
    DB CHECK constraint accepts the three signup keys, so for now we
    persist on the user_acknowledgements row instead (consent_metadata
    JSONB has room).
    """
    try:
        from supabase_storage import get_admin_client
        user_id = request.user["user_id"]
        client = get_admin_client()

        if request.method == "GET":
            # Read the current ack row and return limit_spi info.
            resp = (client.table('user_acknowledgements')
                    .select('consent_metadata')
                    .eq('user_id', user_id)
                    .limit(1)
                    .execute())
            cm = (resp.data[0]['consent_metadata'] if resp.data else None) or {}
            return jsonify({
                "limited": bool(cm.get('limit_spi_confirmed')),
                "confirmed_at": cm.get('limit_spi_confirmed_at'),
            })

        # POST — set the preference + timestamp.
        from datetime import datetime
        ts = datetime.utcnow().isoformat() + "Z"
        resp = (client.table('user_acknowledgements')
                .select('consent_metadata')
                .eq('user_id', user_id)
                .limit(1)
                .execute())
        cm = (resp.data[0]['consent_metadata'] if resp.data else None) or {}
        cm['limit_spi_confirmed'] = True
        cm['limit_spi_confirmed_at'] = ts
        try:
            client.table('user_acknowledgements').update(
                {'consent_metadata': cm}
            ).eq('user_id', user_id).execute()
        except Exception as e:
            logger.warning("limit_spi update failed: %s", e)
            return jsonify({"error": "Failed to record preference"}), 500

        return jsonify({"status": "ok", "limited": True, "confirmed_at": ts})
    except Exception as e:
        logger.exception("limit_sensitive_pi error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/update_cancer_slug", methods=["POST"])
@require_auth
def api_update_cancer_slug():
    """
    Settings → "Change my cancer" flow.

    Body:
      - cancer_slug: str (required, must be a known slug)
      - role: 'patient' | 'caregiver' (optional, defaults to current row value)

    Used after signup when the user wants to switch which cancer WondrChat
    is focused on (e.g. they were misdiagnosed, developed a second primary,
    or want to research a family member's cancer).
    """
    try:
        user_id = request.user["user_id"]
        payload = request.get_json(silent=True) or {}
        slug = (payload.get("cancer_slug") or "").strip().lower()
        role = (payload.get("role") or "patient").strip().lower()
        if role not in ("patient", "caregiver"):
            role = "patient"
        if not slug:
            return jsonify({"error": "cancer_slug is required"}), 400
        try:
            from cancer_registry import exists as _cancer_exists, display_name
        except Exception:
            return jsonify({"error": "cancer registry unavailable"}), 500
        if not _cancer_exists(slug):
            return jsonify({"error": f"Unknown cancer type: {slug}"}), 400

        from supabase_storage import save_cancer_slug
        ok = save_cancer_slug(user_id, slug, role)
        if not ok:
            return jsonify({"error": "Failed to update cancer"}), 500
        return jsonify({
            "status": "ok",
            "cancer_slug": slug,
            "cancer_display": display_name(slug),
            "role": role,
        })
    except Exception as e:
        logger.exception("update_cancer_slug error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/cancer_options", methods=["GET"])
def api_cancer_options():
    """
    Public endpoint — return the list of cancers the user can pick from.

    Used by the signup cancer-picker, the settings change-flow, and the
    chat header badge / sidebar focus card. Only cancers with `ready: true`
    are returned by default; pass ?include_preview=1 to also include
    not-yet-ready cancers.

    Response shape per option:
      {"slug": "colorectal", "display_name": "Colorectal cancer",
       "short_name": "CRC", "ready": true,
       "accent_color": "#1E5C8B", "icon": "shield-check",
       "doc_count": 25, "chunk_count": 1737}

    doc_count + chunk_count are computed from a single Supabase query and
    cached for the lifetime of the lambda. They power the sidebar
    "tailored from N guideline pages" credibility line.
    """
    try:
        include_preview = request.args.get('include_preview') in ('1', 'true', 'yes')
        from cancer_registry import list_all, list_ready, get
        slugs = list_all() if include_preview else list_ready()

        # Per-cancer corpus stats. One query per request (fast — GIN-indexed).
        corpus_stats = {}
        try:
            from supabase_client import get_admin_client
            client = get_admin_client()
            for slug in slugs:
                # Documents whose chunks are tagged with this slug
                doc_q = (client.table('pdf_chunks')
                         .select('document_id', count='exact')
                         .contains('cancer_types', [slug])
                         .limit(1).execute())
                chunk_count = doc_q.count or 0
                # Distinct doc count via a second tiny query
                docs_resp = (client.table('pdf_chunks')
                             .select('document_id')
                             .contains('cancer_types', [slug])
                             .execute())
                doc_ids = {row.get('document_id') for row in (docs_resp.data or []) if row.get('document_id')}
                corpus_stats[slug] = {"doc_count": len(doc_ids), "chunk_count": chunk_count}
        except Exception as _e:
            logger.warning("cancer corpus stats unavailable: %s", _e)

        out = []
        for slug in slugs:
            cfg = get(slug) or {}
            stats = corpus_stats.get(slug, {})
            out.append({
                "slug": slug,
                "display_name": cfg.get("display_name") or slug,
                "short_name": cfg.get("short_name") or cfg.get("display_name") or slug,
                "ready": bool(cfg.get("ready")),
                "accent_color": cfg.get("accent_color") or "#1F5D4F",
                "icon": cfg.get("icon") or "tag",
                "doc_count": stats.get("doc_count", 0),
                "chunk_count": stats.get("chunk_count", 0),
            })
        return jsonify({"options": out})
    except Exception as e:
        logger.exception("cancer_options error")
        return jsonify({"error": str(e), "options": []}), 500


# -------------------------
# Chat History Routes
# -------------------------
@app.route("/api/chat_history", methods=["GET"])
@require_auth
def api_get_chat_history():
    """Load chat history for the authenticated user."""
    try:
        user_id = request.user["user_id"]
        limit = request.args.get("limit", 50, type=int)
        messages = load_chat_history(user_id, limit)
        return jsonify({"messages": messages})
    except Exception as e:
        logger.exception("get_chat_history error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/save_message", methods=["POST"])
@require_auth
def api_save_message():
    """Save a chat message for the authenticated user."""
    try:
        user_id = request.user["user_id"]
        data = request.get_json() or {}
        role = data.get("role")
        content = data.get("content")
        metadata = data.get("metadata")  # Optional metadata (e.g., clinical_trials)

        if not role or not content:
            return jsonify({"error": "role and content are required"}), 400

        if role not in ["user", "assistant"]:
            return jsonify({"error": "role must be 'user' or 'assistant'"}), 400

        success = save_chat_message(user_id, role, content, metadata)
        if success:
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Failed to save message"}), 500
    except Exception as e:
        logger.exception("save_message error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear_chat", methods=["DELETE"])
@require_auth
def api_clear_chat():
    """Clear all chat history for the authenticated user."""
    try:
        user_id = request.user["user_id"]
        success = clear_chat_history(user_id)
        if success:
            return jsonify({"status": "ok", "message": "Chat history cleared"})
        else:
            return jsonify({"error": "Failed to clear chat history"}), 500
    except Exception as e:
        logger.exception("clear_chat error")
        return jsonify({"error": str(e)}), 500


# -------------------------
# Named Conversations (multi-conversation display model)
# Backs the drawer's New chat / Recents / Search. Additive: the legacy
# /api/chat_history + /api/save_message + /api/clear_chat routes above are
# untouched so older installed builds keep working.
# -------------------------
@app.route("/api/conversations", methods=["GET"])
@require_auth
def api_list_conversations():
    """List the authenticated user's conversations (most recent first)."""
    try:
        user_id = request.user["user_id"]
        limit = request.args.get("limit", 100, type=int)
        conversations = list_conversations(user_id, limit)
        return jsonify({"conversations": conversations})
    except Exception as e:
        logger.exception("list_conversations error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations", methods=["POST"])
@require_auth
def api_create_conversation():
    """Create a new conversation for the authenticated user."""
    try:
        user_id = request.user["user_id"]
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        conversation_id = create_conversation(user_id, title)
        if not conversation_id:
            return jsonify({"error": "Failed to create conversation"}), 500
        return jsonify({"id": conversation_id, "title": (title or "New chat")})
    except Exception as e:
        logger.exception("create_conversation error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations/search", methods=["GET"])
@require_auth
def api_search_conversations():
    """Search the authenticated user's conversations by title + content."""
    try:
        user_id = request.user["user_id"]
        query = request.args.get("q", "", type=str)
        results = search_conversations(user_id, query)
        return jsonify({"conversations": results})
    except Exception as e:
        logger.exception("search_conversations error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations/<conversation_id>/messages", methods=["GET"])
@require_auth
def api_conversation_messages(conversation_id):
    """Load display history for one conversation (user-scoped)."""
    try:
        user_id = request.user["user_id"]
        limit = request.args.get("limit", 200, type=int)
        if not conversation_belongs_to_user(user_id, conversation_id):
            return jsonify({"error": "Not found"}), 404
        messages = get_conversation_messages(user_id, conversation_id, limit)
        return jsonify({"messages": messages})
    except Exception as e:
        logger.exception("conversation_messages error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations/<conversation_id>", methods=["PATCH"])
@require_auth
def api_rename_conversation(conversation_id):
    """Rename a conversation (user-scoped)."""
    try:
        user_id = request.user["user_id"]
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not title or not str(title).strip():
            return jsonify({"error": "title is required"}), 400
        success = rename_conversation(user_id, conversation_id, str(title).strip())
        if not success:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.exception("rename_conversation error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
@require_auth
def api_delete_conversation(conversation_id):
    """Delete a conversation and its messages (user-scoped)."""
    try:
        user_id = request.user["user_id"]
        success = delete_conversation(user_id, conversation_id)
        if not success:
            return jsonify({"error": "Failed to delete conversation"}), 500
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.exception("delete_conversation error")
        return jsonify({"error": str(e)}), 500


# -------------------------
# Chat Route
# -------------------------
@app.route("/api/chat", methods=["POST"])
@require_auth
def api_chat():
    """Main chat endpoint."""
    try:
        user_id = request.user["user_id"]

        # Rate limit chat requests
        from rate_limit import check_rate_limit
        allowed, remaining = check_rate_limit(user_id, 'chat', *RATE_LIMIT_CHAT)
        if not allowed:
            return jsonify({"error": "You've reached the message limit. Please wait a bit before sending more."}), 429

        # Consent gate (MHMDA Task 4). If the user has withdrawn collection or
        # sharing consent we cannot lawfully process this query — return 403
        # with a structured payload the frontend uses to surface the consent
        # banner instead of an opaque error.
        try:
            consent_state = get_consent_status(user_id)
        except Exception:
            consent_state = {'chat_disabled': False}
        if consent_state.get('chat_disabled'):
            withdrawn = [k for k in VALID_CONSENT_KEYS
                         if not consent_state.get(k, {}).get('granted', True)]
            return jsonify({
                "error": "Chat is disabled because you've withdrawn one or more required consents. Re-enable them in Settings → Consent Management.",
                "code": "CONSENT_WITHDRAWN",
                "withdrawn": withdrawn,
            }), 403
        # Try to get JSON data from request body
        data = {}
        try:
            raw_data = request.get_data(as_text=True)
            if raw_data:
                data = json.loads(raw_data)
            elif request.is_json:
                data = request.get_json(silent=True) or {}
        except Exception:
            data = {}

        message = data.get("message")
        response_length = data.get("response_length", "normal")
        session_id = data.get("session_id", "default")

        if not message:
            return jsonify({"error": "No message provided"}), 400

        # --- Resolve the conversation for this turn (multi-conversation model) ---
        # New-style clients send a `conversation_id` (a real UUID, or "new"/null
        # to start a fresh thread). Legacy clients omit the field entirely and
        # are mapped to their single 'default' conversation, preserving old
        # behavior. `active_conversation_id` may be None here for a brand-new
        # thread — it's created lazily at persist time so an empty greeting
        # never leaves an orphan conversation.
        has_conversation_field = "conversation_id" in data
        raw_conversation_id = data.get("conversation_id")
        is_new_conversation = False
        if has_conversation_field and raw_conversation_id and raw_conversation_id != "new":
            if conversation_belongs_to_user(user_id, raw_conversation_id):
                active_conversation_id = raw_conversation_id
            else:
                # Unknown / not-owned id → start a fresh conversation instead of
                # writing to someone else's or a non-existent thread.
                active_conversation_id = None
                is_new_conversation = True
        elif has_conversation_field:
            active_conversation_id = None
            is_new_conversation = True
        else:
            # Legacy client: the shared 'default' session, scoped to this user.
            active_conversation_id = get_or_create_conversation(session_id, user_id)

        # Enforce max message length (safety net for frontend maxlength)
        if len(message) > 2000:
            message = message[:2000]

        # Sanitize PII from user message (compliance)
        original_message = message
        message, pii_warnings = sanitize_query(message)
        if pii_warnings:
            # Log PII types detected but NOT the actual values (for privacy)
            pii_types = [w.split(':')[0].strip() if ':' in w else w for w in pii_warnings]
            logger.warning(f"PII detected and sanitized: {len(pii_warnings)} item(s) - types: {pii_types}")

        logger.info(f"Chat request (session: {session_id}): {message[:50]}...")

        # Greeting short-circuit: "hi", "thanks", etc. get a fast canned reply,
        # no LLM call, no retrieval, no resources. Saves ~3s and avoids the
        # full medical-info-dump template on trivial conversational openings.
        try:
            from llm_utils import is_greeting, greeting_response
            if is_greeting(message):
                quick_profile = load_profile(user_id) or {}
                first_name = (quick_profile.get("patient") or {}).get("firstName") or ""
                if not first_name:
                    name = (quick_profile.get("patient") or {}).get("name") or ""
                    first_name = name.split(" ")[0] if name else ""
                logger.info(f"Greeting short-circuit fired for user {user_id}")
                return jsonify({
                    "status": "ok",
                    "answer": greeting_response(first_name),
                    "api_used": "greeting-shortcircuit",
                    "retrieved_count": 0,
                    "sources": [],
                    "citations": {},
                    "resources": [],
                    "followups": [],
                    "guidelines_used": [],
                    "has_guidelines": False,
                })
        except Exception:
            logger.exception("Greeting short-circuit failed (continuing with normal flow)")

        # Load chunks from Supabase
        indexed_chunks = load_all_chunks()

        # Get conversation history from Supabase (user-scoped, by conversation
        # id). A brand-new thread has no prior context.
        history = (get_conversation_history_by_id(active_conversation_id, user_id)
                   if active_conversation_id else [])
        conversation_context = format_conversation_context(history)

        # Load patient profile from Supabase
        patient_profile = load_profile(user_id)
        # load_profile returns {} if not found, which is falsy in Python.
        # We want to ensure extract_patient_context_complex is called even if profile is mostly empty.
        patient_context = extract_patient_context_complex(patient_profile) if (patient_profile is not None and len(patient_profile) > 0) else {}

        # Derive cancer slug from the loaded profile, falling back to the user's
        # persisted selection (so the chat trial-search uses the right condition
        # synonyms instead of the legacy 'colorectal' default).
        # Threaded through retrieval (chunk filter) + LLM generators (overlay).
        cancer_slug = _resolve_cancer_slug(user_id, patient_profile)
        cancer_types_filter = [cancer_slug, 'general'] if cancer_slug else None
        patient_context['cancer_slug'] = cancer_slug

        # ----- SAFETY CLASSIFIER (supervisor mandate 2026-07-21) ----------
        # Supersedes the crisis short-circuit. Every inbound message is
        # tiered (T1/T2/T3/MH/NONE) by lib/safety_classifier BEFORE the chat
        # model: deterministic keyword floor + LLM judgment layer that can
        # only raise the tier. Started HERE and joined right after retrieval
        # so the ~0.6s LLM call runs concurrently with hybrid_search and
        # adds ~0 wall-clock. T1/T2/MH short-circuit with an escalation
        # card; T3 rides alongside the normal reply as a banner; the LLM
        # never sees a T1/T2/MH message, so it cannot soften the response.
        safety_future = None
        safety_executor = None
        try:
            from concurrent.futures import ThreadPoolExecutor
            from safety_classifier import classify_message, SafetyResult

            _tx_summary = str(patient_context.get('current_treatments') or '')
            _on_active_tx = bool(patient_context.get('current_regimen')) or \
                ('active' in _tx_summary.lower())

            def _run_safety_classifier() -> "SafetyResult":
                _perspective = 'self'
                try:
                    from supabase_storage import get_account_basics
                    _basics = get_account_basics(user_id) or {}
                    _perspective = _basics.get('perspective') or 'self'
                except Exception:
                    pass
                return classify_message(
                    message,
                    on_active_treatment=_on_active_tx,
                    perspective=_perspective,
                )

            safety_executor = ThreadPoolExecutor(max_workers=1)
            safety_future = safety_executor.submit(_run_safety_classifier)
        except Exception:
            logger.exception("Safety classifier failed to start (continuing)")

        # Classify query type early — it drives both the symptom-context injection
        # below and the chunk-retrieval top_k. Must be set before any branch reads it.
        query_type = classify_query_type(message)

        # Inject recent symptom check-in data for side_effect/treatment queries
        if query_type in ('side_effect', 'treatment'):
            try:
                from supabase_storage import load_latest_screening_score
                latest_symptoms = load_latest_screening_score(user_id, 'SYMPTOM')
                if latest_symptoms and latest_symptoms.get('scores'):
                    symptom_names = ['Nausea', 'Fatigue', 'Diarrhea', 'Neuropathy', 'Pain',
                                     'Appetite loss', 'Mouth sores', 'Hand-foot syndrome', 'Constipation', 'Skin rash']
                    reported = []
                    for idx, name in enumerate(symptom_names):
                        score = latest_symptoms['scores'].get(str(idx), 0)
                        if score >= 2:
                            severity = ['', 'mild', 'moderate', 'severe', 'very severe'][min(score, 4)]
                            reported.append(f"{name} ({severity})")
                    if reported:
                        patient_context['recent_symptom_report'] = reported
                        patient_context['symptom_report_date'] = latest_symptoms.get('completed_at', '')
            except Exception:
                logger.debug("Could not load symptom data for context")

        # Check for cancer type mismatch
        mismatch_detected = False
        if patient_context.get('cancer_type'):
            cancer_keywords = ['breast cancer', 'lung cancer', 'prostate cancer', 'colon cancer',
                             'colorectal', 'pancreatic', 'ovarian', 'melanoma']
            user_message_lower = message.lower()
            patient_cancer = patient_context.get('cancer_type', '').lower()

            for cancer_type in cancer_keywords:
                if cancer_type in user_message_lower:
                    if cancer_type not in patient_cancer and patient_cancer not in cancer_type:
                        mismatch_detected = True
                        break

        effective_top_k = 8 if query_type in ('treatment', 'clinical_trial') else 5

        # Search relevant chunks (hybrid: TF + vector with RRF)
        retrieved = []
        try:
            retrieved = hybrid_search(message, indexed_chunks, top_k=effective_top_k, cancer_types=cancer_types_filter)
            logger.info(f"hybrid_search returned {len(retrieved)} chunks (top_k={effective_top_k}, query_type={query_type}, cancer_types={cancer_types_filter})")
        except Exception:
            logger.exception("hybrid_search failed, falling back to TF-only")
            try:
                retrieved = search_chunks(message, indexed_chunks, top_k=effective_top_k)
            except Exception:
                logger.exception("search_chunks also failed")

        # ----- SAFETY CLASSIFIER JOIN -------------------------------------
        # Retrieval is done; collect the classifier result (usually already
        # finished). classify_message has its own internal timeout and never
        # raises; the outer timeout only guards a wedged thread.
        safety_result = None
        if safety_future is not None:
            try:
                safety_result = safety_future.result(timeout=6)
            except Exception:
                logger.exception("Safety classifier join failed (continuing)")
            finally:
                try:
                    safety_executor.shutdown(wait=False)
                except Exception:
                    pass
        safety_tier = safety_result.tier if safety_result else 'NONE'

        if safety_result is not None and safety_tier != 'NONE':
            try:
                from supabase_storage import log_safety_classification
                log_safety_classification(
                    user_id, active_conversation_id, message, safety_result)
            except Exception:
                logger.warning("safety classification logging failed")

        if safety_tier in ('T1', 'T2', 'MH'):
            # Escalation card INSTEAD of a chat reply. Legacy fields
            # (is_crisis / crisis_resources / crisis_category / urgency) are
            # preserved for older clients; the new `safety` block carries the
            # tier card. The chat LLM never sees this message.
            from confidence import render_crisis_response, crisis_resources_for
            from safety_classifier import render_patient_line
            from safety_rules import emergency_number, rules_version

            _legacy_cat = {
                'MH': 'self_harm',
                'T1': 'medical_emergency',
                'T2': 'urgent_oncology',
            }[safety_tier]
            _crisis_res = crisis_resources_for(_legacy_cat)
            _level = 'EMERGENCY' if safety_tier in ('T1', 'MH') else 'URGENT'
            _perspective = 'self'
            _patient_first = None
            try:
                from supabase_storage import get_account_basics
                _b = get_account_basics(user_id) or {}
                _perspective = _b.get('perspective') or 'self'
                _patient = (patient_profile or {}).get('patient') or {}
                _patient_first = _patient.get('firstName') or None
            except Exception:
                pass
            _line = render_patient_line(
                safety_tier, _perspective, _patient_first)
            logger.warning(
                f"SAFETY_ESCALATION tier={safety_tier} "
                f"category={safety_result.category} "
                f"source={safety_result.source} "
                f"rule_matched={safety_result.rule_matched}"
            )
            return jsonify({
                "answer": render_crisis_response(_legacy_cat),
                "api_used": "safety-classifier",
                "retrieved_count": 0,
                "response_length": response_length,
                "patient_context_used": False,
                "mismatch_detected": False,
                "pii_filtered": False,
                "validation_warnings": [],
                "medical_safety_check": True,
                "conversation_length": len(history),
                "has_profile_updates": False,
                "profile_updates_saved": None,
                "sources": [],
                "citations": {},
                "resources": [],
                "followups": [],
                "guidelines_used": [],
                "has_guidelines": False,
                "clinical_trials": None,
                "urgency": {
                    "detected": True,
                    "level": _level,
                    "guidance": _line or _crisis_res.get("message"),
                },
                "is_crisis": True,
                "crisis_resources": _crisis_res,
                "crisis_category": _legacy_cat,
                "safety": {
                    "tier": safety_tier,
                    "category": safety_result.category,
                    "patient_line": _line,
                    "rule_matched": safety_result.rule_matched,
                    "confidence": safety_result.confidence,
                    "emergency_number": emergency_number(),
                    "offer_symptom_log": safety_tier == 'T2',
                    "rules_version": rules_version(),
                },
                "debug_info": {
                    "api_used": "safety-classifier",
                    "safety_source": safety_result.source,
                },
            })

        # Off-topic detection — refuse with redirect if query is outside scope.
        # Any non-NONE safety tier (i.e. T3 here) is in-domain BY DEFINITION:
        # symptom-described emergencies without oncology vocab ("passing a lot
        # of blood from my rectum") used to die on this gate.
        try:
            from confidence import is_in_oncology_domain, render_off_topic_response
            if safety_tier == 'NONE':
                on_topic, ot_reason = is_in_oncology_domain(message, retrieved)
                if not on_topic:
                    logger.info(f"Off-topic query refused: {ot_reason}")
                    return jsonify({
                        "status": "ok",
                        "answer": render_off_topic_response(cancer_slug),
                        "api_used": "off-topic-filter",
                        "retrieved_count": 0,
                        "off_topic": True,
                        "sources": [],
                        "guidelines_used": [],
                        "has_guidelines": False,
                    })
        except Exception:
            logger.exception("Off-topic detection failed (continuing with normal flow)")

        # --- Lifecycle question policy: pick at most ONE gentle "getting to
        # know you" topic for this turn. Pure python (no LLM); assemble_prompt
        # drops the directive itself if its urgency detection fires.
        question_directive = None
        coverage = None
        connections_summary = None
        try:
            from question_policy import compute_coverage, select_next_question
            profile_for_policy = patient_profile if isinstance(patient_profile, dict) else {}
            coverage = compute_coverage(profile_for_policy, cancer_slug)
            model_state_view = profile_for_policy.get("model_state") or {}
            pending_now = ((profile_for_policy.get("beliefs") or {}).get("pending") or [])

            # Modeler consumers (Push 2) — dormant until FEATURE_MODELER_ACTIVE.
            expectation_candidates = None
            try:
                from datetime import datetime as _dt
                from modeler import (
                    expectation_question_candidates, modeler_active,
                    render_connections_summary,
                )
                if modeler_active():
                    connections_view = profile_for_policy.get("connections") or {}
                    connections_summary = render_connections_summary(connections_view, _dt.utcnow())
                    expectation_candidates = expectation_question_candidates(
                        connections_view, _dt.utcnow())
            except Exception:
                logger.exception("Modeler consumers failed (continuing without)")

            question_directive = select_next_question(coverage, model_state_view, {
                "query_type": query_type,
                "question_marks": message.count("?"),
                "response_length": response_length,
                "has_pending_confirmations": bool(pending_now),
                "register": model_state_view.get("register"),
            }, expectation_candidates=expectation_candidates)
        except Exception:
            logger.exception("Question policy failed (continuing without a question)")

        # Assemble prompt
        if mismatch_detected:
            message_with_note = f"{message}\n\n[SYSTEM NOTE: User asked about different cancer type than their profile]"
            prompt, prompt_metadata = assemble_prompt(message_with_note, retrieved, patient_profile, response_length,
                                    conversation_context, patient_context,
                                    question_directive=question_directive,
                                    connections_summary=connections_summary)
        else:
            prompt, prompt_metadata = assemble_prompt(message, retrieved, patient_profile, response_length,
                                    conversation_context, patient_context,
                                    question_directive=question_directive,
                                    connections_summary=connections_summary)

        # Check LLM availability
        llm_status = get_llm_status()
        if not llm_status["primary_api"]:
            return jsonify({
                "error": "No LLM API available. Please check TOGETHER_API_KEY or GROQ_API_KEY.",
                "debug_info": llm_status
            }), 500

        # PII leak guard (Task 10). Last-chance check before the de-identified
        # payload leaves our perimeter. Belt-and-suspenders: the upstream
        # de-identification already runs, but a regression in any of the
        # composition steps could leak. We log + raise so the failure is
        # visible AND blocked, then return a 500 to the caller rather than
        # ship leaky data.
        #
        # Scope: scan only the PHI-bearing components (user message +
        # de-identified patient context/profile/conversation), NOT the fully
        # assembled prompt. Retrieved guideline chunks are public documents
        # whose version dates ("05/12/2026") and site addresses trip the
        # date/address patterns and block legitimate questions.
        try:
            from deidentify import detect_pii_leaks
            guard_payload = prompt_metadata.pop('pii_guard_payload', None)
            leaks = detect_pii_leaks(guard_payload if guard_payload is not None else prompt)
            if leaks:
                # Truncate detail so the log entry doesn't itself contain the PII
                summary = [name for name, _snip in leaks][:8]
                logger.error("PII-LEAK-BLOCKED categories=%s count=%d", summary, len(leaks))
                return jsonify({
                    "error": "Request blocked by privacy guard. Please rephrase your question without including names, dates of birth, addresses, phone numbers, or other identifying details.",
                    "code": "PII_LEAK_BLOCKED",
                }), 500
        except Exception as _e:
            # If the guard itself crashes we don't want to take chat down — log
            # and proceed. The upstream de-identification is still active.
            logger.warning("PII guard crashed: %s", _e)

        # Call LLM with smart routing (query_type already classified above)
        try:
            answer, api_used = call_llm(prompt, response_length, query=message, query_type=query_type)
            if not answer:
                raise RuntimeError("LLM returned empty response")

            answer = trim_incomplete_sentence(answer)
            logger.info(f"{api_used.upper()} response success - length: {len(answer)}")

            # Validate response
            validation = validate_response(answer, message, patient_context)
            medical_validation = enhanced_medical_validation(answer, message)

            all_warnings = validation['warnings'] + medical_validation['flags']
            if all_warnings:
                logger.warning(f"Response validation warnings: {all_warnings}")

            final_answer = validation['enhanced_response']

            # Second-pass verification — fact-check against retrieved chunks
            verification_result = {'verified': True, 'recommended_action': 'pass', 'verifier_used': 'skipped'}
            try:
                from verify import verify_response, HEDGED_FALLBACK_RESPONSE, SOFT_DISCLAIMER_PREFIX
                verification_result = verify_response(final_answer, retrieved, message)

                if verification_result.get('recommended_action') == 'add_disclaimer':
                    final_answer = SOFT_DISCLAIMER_PREFIX + final_answer
                    logger.info("Verification: added soft disclaimer")
                elif verification_result.get('recommended_action') == 'regenerate':
                    logger.info("Verification: regenerating with stronger hedging")
                    # Regenerate with hedge instruction prepended
                    hedged_prompt = ("CRITICAL: The previous response had unsupported claims. "
                                     "You MUST hedge heavily. If specific details are not in the sources, "
                                     "say 'I don't have reliable information on this' rather than fabricate.\n\n" + prompt)
                    try:
                        retry_answer, retry_api = call_llm(hedged_prompt, response_length, query=message, query_type=query_type)
                        if retry_answer:
                            retry_answer = trim_incomplete_sentence(retry_answer)
                            retry_validation = validate_response(retry_answer, message, patient_context)
                            retry_verification = verify_response(retry_validation['enhanced_response'], retrieved, message)
                            if retry_verification.get('verified'):
                                final_answer = retry_validation['enhanced_response']
                                verification_result = retry_verification
                                logger.info("Verification: regeneration succeeded")
                            else:
                                # Both attempts failed verification — return hedged fallback
                                final_answer = HEDGED_FALLBACK_RESPONSE
                                verification_result = retry_verification
                                logger.warning("Verification: both attempts failed — using hedged fallback")
                    except Exception as _e:
                        logger.exception("Regeneration failed; keeping original with disclaimer")
                        final_answer = SOFT_DISCLAIMER_PREFIX + final_answer
            except Exception:
                logger.exception("Verification step failed (continuing with original response)")

            # Feature 1: Inline citation post-processing.
            # Strips invalid [N] markers and builds the citation_map for the frontend.
            # Run before resources_text is appended (resources contain no [N] markers).
            citation_map = {}
            if feature_enabled('inline_citations'):
                try:
                    final_answer, citation_map = postprocess_citations(final_answer, retrieved)
                except Exception:
                    logger.exception("Citation post-processing failed; continuing without inline citations")
                    citation_map = {}

            # Phase B.1: parse the trailing FOLLOWUPS: block out of the answer
            # so the frontend can render them as interactive chips below the bubble.
            followups = []
            try:
                from llm_utils import extract_followups
                final_answer, followups = extract_followups(final_answer)
            except Exception:
                logger.exception("Follow-up extraction failed; continuing without chips")
                followups = []

            # Tone softener — belt-and-suspenders for "you should / you must".
            # The system prompt forbids these phrases but LLMs slip ~5-22% of the
            # time. Substituting in-place is cheap and idempotent; per-pattern
            # counts logged for telemetry.
            tone_meta = {"substitutions": 0, "by_pattern": {}}
            try:
                from llm_utils import soften_tone
                final_answer, tone_meta = soften_tone(final_answer)
            except Exception:
                logger.exception("Tone softener failed; continuing with raw answer")

            # Pull relevant patient resources as a structured list. They render in
            # a subdued row below the bubble (frontend), NOT inline in the answer
            # text. The legacy behavior of appending a "📚 link | link | link"
            # block to final_answer was noisy on every response.
            resources_list = []
            if response_length != "brief":
                try:
                    resources_list = get_relevant_resources(query_type, include_resources=True, query=message) or []
                except Exception:
                    logger.exception("Resource lookup failed; continuing without resources")
                    resources_list = []

            # --- Feature: Clinical Trials Search ---
            # Return trials data separately for frontend rendering (not as markdown in answer)
            clinical_trials_data = None
            if is_clinical_trial_query(message) and patient_context:
                try:
                    logger.info(f"Clinical trial query detected for user {user_id}")

                    # Pre-search validation: check if profile has enough data
                    readiness = validate_trial_search_readiness(patient_context)
                    if not readiness["ready"]:
                        clinical_trials_data = {
                            "error": "incomplete_profile",
                            "message": readiness["prompt_message"],
                            "missing_critical": readiness["missing_critical"],
                            "missing_helpful": readiness["missing_helpful"],
                            "just_in_time_question": readiness.get("just_in_time_question"),
                            "chat_prefill": readiness.get("chat_prefill"),
                        }
                    else:
                        # Graph-aware ranking (Push 3): the Modeler's per-patient
                        # graph adjusts ordering + rationale when active.
                        from modeler import modeler_active
                        trial_connections = ((patient_profile or {}).get("connections")
                                             if modeler_active() else None)
                        trials_result = search_trials_for_patient(
                            patient_context, max_results=5, radius_miles=100,
                            connections=trial_connections)
                        if not trials_result.get("error"):
                            # Return full trials data for frontend rendering
                            clinical_trials_data = {
                                "found": len(trials_result.get("trials", [])),
                                "total": trials_result.get("total_found", 0),
                                "trials": trials_result.get("trials", []),
                                "search_criteria": trials_result.get("search_criteria", {})
                            }
                            # Include profile completeness tip if helpful fields are missing
                            if readiness.get("prompt_message"):
                                clinical_trials_data["profile_completeness"] = readiness["prompt_message"]
                            logger.info(f"Found {clinical_trials_data['found']} clinical trials for user")
                            _emit_trials_shown(user_id, "chat", trials_result,
                                               session_id=active_conversation_id or session_id)
                        elif trials_result.get("error") == "no_zip_code":
                            clinical_trials_data = {
                                "error": "no_zip_code",
                                "message": "To search for clinical trials near you, please add your zip code to your profile."
                            }
                except Exception as e:
                    logger.error(f"Error searching clinical trials: {e}", exc_info=True)

            # Phase D — Trial-search auto-fire. When the trial cards pipeline
            # produced real matches, replace the LLM essay with a concise
            # lead-in so the cards become the primary content. We also drop
            # follow-ups and resources for this case — the cards carry their
            # own context, footer links, and CTAs.
            if (clinical_trials_data and isinstance(clinical_trials_data, dict)
                    and clinical_trials_data.get("trials")
                    and not clinical_trials_data.get("error")):
                final_answer = (
                    "Here are clinical trials that match your profile. "
                    "Tap any card for details, or save trials to your watchlist for later."
                )
                followups = []
                resources_list = []
                citation_map = {}

            # NOTE: this turn is persisted to the conversation store AFTER
            # response_data is assembled below, so the stored assistant message
            # matches exactly what the client renders (final answer + metadata:
            # sources, citations, follow-ups, clinical trials). See the
            # "Persist this turn" block just before the return.

            # --- Feature 1: Scan for profile updates ---
            # Legacy v1 remains the profile WRITER. When shadow mode is on
            # (FEATURE_EXTRACTION_SHADOW=true; env read directly — the
            # feature_enabled() helper defaults to TRUE and must not gate a
            # dormant feature), extraction v2 (extract+reconcile) runs on the
            # same turn and records its would-be decisions as
            # patient_events(kind='shadow_extraction') WITHOUT touching the
            # profile. To keep one extractor LLM call per turn, v2's merged
            # candidates are converted back to the v1 patch shape for the
            # legacy write instead of calling the v1 extractor separately.
            profile_updates = {}
            update_success = False
            pending_confirmations = []
            try:
                beliefs_write = os.getenv("FEATURE_BELIEFS_WRITE", "false").lower() == "true"
                shadow_on = os.getenv("FEATURE_EXTRACTION_SHADOW", "false").lower() == "true"

                if beliefs_write:
                    # Extraction v2 IS the writer: beliefs + materialized
                    # profile + pending-confirmation queue ("is that right?"
                    # chips). update_profile_with_sources is retired from the
                    # chat path (the wizard still uses it).
                    from patient_model import (
                        absorb_form_profile, apply_decisions, extract_facts,
                        reconcile, update_register_signal,
                    )
                    profile_obj = patient_profile if isinstance(patient_profile, dict) else {}
                    # Lazy-sync: materialized fields with no belief yet (legacy
                    # stragglers) get one, so conflicts/negations have a prior.
                    absorb_form_profile(profile_obj, only_missing=True)
                    candidates = extract_facts(original_message, profile_obj)
                    beliefs_view = profile_obj.get("beliefs") or \
                        {"version": 1, "fields": {}, "pending": []}
                    decisions = reconcile(candidates, beliefs_view)
                    update_register_signal(original_message, profile_obj)
                    apply_res = apply_decisions(
                        user_id, profile_obj, decisions,
                        session_id=(active_conversation_id or session_id), shadow=False,
                    )
                    pending_confirmations = [
                        {"id": p["id"], "path": p["path"], "prompt": p["prompt"],
                         "proposed_value": p["proposed_value"]}
                        for p in apply_res.pending_confirmations
                    ]
                    profile_updates = {path: True for path in apply_res.committed_paths}
                    update_success = bool(apply_res.committed_paths)
                    if profile_updates:
                        logger.info(f"Belief updates for user {user_id}: {sorted(profile_updates.keys())}")
                elif shadow_on:
                    from patient_model import (
                        apply_decisions, candidates_to_v1_updates, extract_facts, reconcile,
                    )
                    candidates = extract_facts(original_message, patient_profile or {})
                    beliefs_view = (patient_profile or {}).get("beliefs") or \
                        {"version": 1, "fields": {}, "pending": []}
                    decisions = reconcile(candidates, beliefs_view)
                    if decisions:
                        apply_decisions(
                            user_id, patient_profile or {}, decisions,
                            session_id=(active_conversation_id or session_id), shadow=True,
                        )
                    profile_updates = candidates_to_v1_updates(candidates)
                else:
                    profile_updates = extract_profile_updates_from_query(
                        original_message, patient_profile or {})

                if profile_updates and not beliefs_write:
                    logger.info(f"Detected profile updates for user {user_id}: {list(profile_updates.keys())}")
                    source_info = {
                        "source_type": "chat",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat()
                    }
                    update_success = update_profile_with_sources(user_id, profile_updates, source_info)
                    if update_success:
                        logger.info(f"Successfully updated profile for user {user_id}")
                    else:
                        logger.error(f"Failed to save profile updates for user {user_id}")
            except Exception as e:
                logger.error(f"Error in profile update scanning: {e}", exc_info=True)

            # --- Lifecycle bookkeeping: question cooldowns + stage ladder ---
            lifecycle_stage = None
            try:
                from question_policy import advance_lifecycle_stage, compute_coverage, record_turn
                from supabase_storage import (
                    append_patient_event, save_model_state, update_lifecycle_stage_column,
                )
                profile_for_policy = patient_profile if isinstance(patient_profile, dict) else {}
                model_state = profile_for_policy.setdefault("model_state", {})
                # Only count the topic as asked if assemble_prompt actually
                # rendered the directive (it drops it on urgent turns).
                record_turn(model_state, prompt_metadata.get("question_topic_asked"))
                fresh_coverage = compute_coverage(profile_for_policy, cancer_slug)
                model_state["coverage_score"] = fresh_coverage["score"]
                lifecycle_stage, stage_changed = advance_lifecycle_stage(profile_for_policy, fresh_coverage)
                save_model_state(user_id, model_state)
                if stage_changed:
                    update_lifecycle_stage_column(user_id, lifecycle_stage)
                    append_patient_event(user_id, "stage_transition",
                                         payload={"stage": lifecycle_stage,
                                                  "coverage": fresh_coverage["score"]},
                                         source="system",
                                         session_id=(active_conversation_id or session_id))
                if prompt_metadata.get("question_topic_asked"):
                    append_patient_event(user_id, "question_asked",
                                         payload={"topic": prompt_metadata["question_topic_asked"]},
                                         source="system",
                                         session_id=(active_conversation_id or session_id))
            except Exception:
                logger.exception("Lifecycle bookkeeping failed (non-fatal)")

            # Extract sources for the frontend panel
            sources_metadata = []
            guidelines_used = []
            guideline_keywords = ['NCCN', 'guideline', 'ACS', 'ASCO', 'CDC', 'NCI', 'recommendation']
            try:
                from llm_utils import get_friendly_source_name
                seen_sources = set()
                for chunk in retrieved[:5]:  # max 5 sources per response
                    if isinstance(chunk, dict) and chunk.get('filename'):
                        fname = chunk['filename']
                        if fname not in seen_sources:
                            content = chunk.get('content', '') or ''
                            preview = content[:140].strip()
                            if len(content) > 140:
                                preview += '...'
                            sources_metadata.append({
                                "title": fname,
                                "display_name": get_friendly_source_name(fname),
                                "type": "document",
                                "section": chunk.get('chunk_index'),
                                "preview": preview,
                            })
                            seen_sources.add(fname)

                            fname_lower = fname.lower()
                            if any(kw.lower() in fname_lower for kw in guideline_keywords):
                                guidelines_used.append(fname)

                for s in sources_metadata:
                    if "Comprehensive_Colon_Cancer_Guide" in s["title"]:
                        s["is_featured"] = True
            except Exception as e:
                logger.error(f"Error extracting source metadata: {e}", exc_info=True)

            # T3 (same-day) banner: the classifier's verdict wins over the
            # prompt-injection urgency so exactly ONE banner renders, and the
            # structured safety block rides along for the card UI.
            safety_block = None
            t3_urgency = None
            if safety_result is not None and safety_tier == 'T3':
                try:
                    from safety_classifier import render_patient_line
                    from safety_rules import emergency_number, rules_version
                    _t3_line = render_patient_line('T3', 'self', None)
                    t3_urgency = {
                        "detected": True,
                        "level": "SAME_DAY",
                        "guidance": _t3_line,
                    }
                    safety_block = {
                        "tier": "T3",
                        "category": safety_result.category,
                        "patient_line": _t3_line,
                        "rule_matched": safety_result.rule_matched,
                        "confidence": safety_result.confidence,
                        "emergency_number": emergency_number(),
                        "offer_symptom_log": False,
                        "rules_version": rules_version(),
                    }
                except Exception:
                    logger.exception("T3 safety block build failed")

            # Build response
            response_data = {
                "answer": final_answer,
                "api_used": api_used,
                "retrieved_count": len(retrieved),
                "response_length": response_length,
                "patient_context_used": bool(patient_context),
                "mismatch_detected": mismatch_detected,
                "pii_filtered": len(pii_warnings) > 0,
                "validation_warnings": all_warnings,
                "medical_safety_check": medical_validation['safe'],
                "conversation_length": len(history) + 1,
                "has_profile_updates": bool(profile_updates),
                "profile_updates_saved": update_success if profile_updates else None,
                "sources": sources_metadata,
                "citations": citation_map,
                "resources": resources_list,
                "followups": followups,
                "guidelines_used": guidelines_used,
                "has_guidelines": len(guidelines_used) > 0,
                "clinical_trials": clinical_trials_data,
                "pending_confirmations": pending_confirmations or None,
                "lifecycle_stage": lifecycle_stage,
                "urgency": t3_urgency or ({
                    "detected": prompt_metadata.get('urgency_detected', False),
                    "level": prompt_metadata.get('urgency_level'),
                    "guidance": prompt_metadata.get('urgency_guidance', '')
                } if prompt_metadata.get('urgency_detected') else None),
                "safety": safety_block,
                "debug_info": {
                    "api_used": api_used,
                    "retrieved_count": len(retrieved),
                    "has_patient_profile": bool(patient_profile),
                    "query_type": query_type,
                    "session_id": session_id,
                    "verification": {
                        "verified": verification_result.get('verified'),
                        "fabrication_risk": verification_result.get('fabrication_risk'),
                        "action": verification_result.get('recommended_action'),
                        "verifier_used": verification_result.get('verifier_used'),
                    },
                    "retrieval_confidence": prompt_metadata.get('retrieval_confidence', {}),
                }
            }

            # If profile was updated successfully, include the updated context
            if profile_updates and update_success:
                # Reload the updated profile to get fresh context
                updated_profile = load_profile(user_id)
                if updated_profile:
                    updated_context = extract_patient_context_complex(updated_profile)
                    response_data["updated_profile_context"] = updated_context
                    response_data["profile_update_fields"] = list(profile_updates.keys())

            # --- Persist this turn to the conversation store ---
            # Single source of truth for the multi-conversation display model.
            # Brand-new threads are created lazily here (only real exchanges get
            # a conversation). The assistant message carries the same render
            # metadata the client shows, so history survives a relaunch intact.
            try:
                if not active_conversation_id:
                    active_conversation_id = create_conversation(user_id)
                    is_new_conversation = True
                if active_conversation_id:
                    assistant_metadata = {
                        "sources": response_data.get("sources", []),
                        "citations": response_data.get("citations", {}),
                        "followups": response_data.get("followups", []),
                        "resources": response_data.get("resources", []),
                        "urgency": response_data.get("urgency"),
                        "clinical_trials": response_data.get("clinical_trials"),
                        "pending_confirmations": response_data.get("pending_confirmations"),
                        "api_used": response_data.get("api_used"),
                    }
                    append_qa_to_conversation(
                        active_conversation_id, user_id, message,
                        response_data["answer"], metadata=assistant_metadata,
                    )
                response_data["conversation_id"] = active_conversation_id
                # On the first turn the server auto-titles from the message;
                # echo that back so the client can label the thread immediately.
                if is_new_conversation and active_conversation_id:
                    fresh = list_conversations(user_id, limit=1)
                    response_data["title"] = fresh[0]["title"] if fresh else None
            except Exception:
                logger.exception("Failed to persist conversation turn")

            return jsonify(response_data)

        except Exception as e:
            logger.exception(f"LLM API generation failed: {e}")
            return jsonify({
                "error": f"LLM API failed: {str(e)}",
                "debug_info": llm_status
            }), 500

    except Exception as e:
        logger.exception("Unexpected /chat error")
        return jsonify({"error": str(e)}), 500

# -------------------------
# Feedback Route
# -------------------------
@app.route("/api/feedback", methods=["POST"])
@require_auth
def api_feedback():
    """Save user feedback on bot responses."""
    try:
        user_id = request.user["user_id"]

        data = request.get_json(silent=True) or {}
        rating = data.get("rating")  # "up" or "down"
        message_preview = data.get("message_preview", "")[:200]

        if rating not in ("up", "down"):
            return jsonify({"error": "Invalid rating"}), 400

        # Store in Supabase chat_feedback table (create if needed)
        try:
            client = get_supabase_client()
            client.table("chat_feedback").insert({
                "user_id": user_id,
                "rating": rating,
                "message_preview": message_preview
            }).execute()
        except Exception as e:
            # Table may not exist yet — log but don't fail
            logger.warning(f"Could not save feedback (table may not exist): {e}")

        return jsonify({"status": "ok"})
    except Exception as e:
        logger.exception("Feedback error")
        return jsonify({"error": str(e)}), 500

# -------------------------
# Data Sources Route
# -------------------------
@app.route("/api/data_sources", methods=["GET"])
def api_data_sources():
    """Get list of PDF data sources."""
    try:
        metadata = get_document_metadata()

        return jsonify({
            "status": "ok",
            "data_sources": metadata,
            "total_count": len(metadata),
            "total_chunks": sum(doc.get('chunk_count', 0) for doc in metadata)
        })
    except Exception as e:
        logger.exception("get_data_sources error")
        return jsonify({"error": str(e)}), 500


# -------------------------
# Screening Endpoints (Items 3, 4, 5 - PHQ-9/GAD-7/PSS-10/ISI)
# -------------------------
@app.route("/api/screening/save", methods=["POST"])
@require_auth
def api_save_screening():
    """Save a completed screening instrument score."""
    try:
        user_id = request.user["user_id"]
        data = request.get_json(silent=True) or {}

        instrument = data.get('instrument')  # PHQ9, GAD7, PSS10, ISI, PREMM5, SYMPTOM
        scores = data.get('scores', {})
        total_score = data.get('total_score')
        severity_label = data.get('severity_label', '')

        if not instrument or total_score is None:
            return jsonify({"error": "instrument and total_score required"}), 400

        valid_instruments = ['PHQ9', 'GAD7', 'PSS10', 'ISI', 'PREMM5', 'SYMPTOM']
        if instrument not in valid_instruments:
            return jsonify({"error": f"instrument must be one of {valid_instruments}"}), 400

        # Crisis check: PHQ-9 Q9 (suicidal ideation)
        is_crisis = False
        crisis_resources = None
        if instrument == 'PHQ9':
            q9_score = scores.get('q9', 0)
            if isinstance(q9_score, (int, float)) and q9_score >= 1:
                is_crisis = True
                crisis_resources = {
                    "message": "You indicated thoughts of self-harm. Please reach out for support immediately.",
                    "resources": [
                        {"name": "988 Suicide & Crisis Lifeline", "contact": "Call or text 988"},
                        {"name": "Crisis Text Line", "contact": "Text HOME to 741741"},
                        {"name": "Emergency Services", "contact": "Call 911"}
                    ]
                }

        from supabase_storage import save_screening_score
        success = save_screening_score(user_id, instrument, scores, total_score, severity_label)

        return jsonify({
            "status": "ok" if success else "error",
            "is_crisis": is_crisis,
            "crisis_resources": crisis_resources,
            "total_score": total_score,
            "severity_label": severity_label
        })
    except Exception as e:
        logger.exception("Screening save error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/screening/load", methods=["GET"])
@require_auth
def api_load_screening():
    """Load most recent screening scores for all instruments."""
    try:
        user_id = request.user["user_id"]
        from supabase_storage import load_latest_screening_score

        result = {}
        for instrument in ['PHQ9', 'GAD7', 'PSS10', 'ISI', 'SYMPTOM', 'PREMM5']:
            score_data = load_latest_screening_score(user_id, instrument)
            if score_data:
                result[instrument] = score_data

        return jsonify({"status": "ok", "scores": result})
    except Exception as e:
        logger.exception("Screening load error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/screening/history", methods=["GET"])
@require_auth
def api_screening_history():
    """Load screening history for all instruments (for dashboard charts)."""
    try:
        user_id = request.user["user_id"]
        from supabase_storage import load_all_screening_history
        history = load_all_screening_history(user_id)
        return jsonify({"status": "ok", "history": history})
    except Exception as e:
        logger.exception("Screening history error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/surveillance", methods=["GET"])
@require_auth
def api_surveillance():
    """Generate personalized surveillance schedule from patient profile."""
    try:
        user_id = request.user["user_id"]
        from supabase_storage import load_profile
        profile = load_profile(user_id)
        if not profile:
            return jsonify({"status": "ok", "schedule": None, "message": "No profile found"})

        stage = profile.get('primaryDiagnosis', {}).get('stage', '')
        surgery_date = None
        for s in profile.get('surgicalHistory', []):
            if isinstance(s, dict) and s.get('date'):
                surgery_date = s['date']
                break

        diagnosis_date = profile.get('primaryDiagnosis', {}).get('dateOfDiagnosis')

        if not stage or not surgery_date:
            return jsonify({"status": "ok", "schedule": None,
                           "message": "Stage and surgery date needed for surveillance schedule"})

        try:
            from profile_validator import derive_universal_core as _derive_core
            _surv_slug = _derive_core(profile or {}).get('cancer_slug') or 'colorectal'
        except Exception:
            _surv_slug = 'colorectal'

        from surveillance import generate_surveillance_schedule
        schedule = generate_surveillance_schedule(stage, surgery_date, cancer_slug=_surv_slug,
                                                   diagnosis_date=diagnosis_date)
        return jsonify({"status": "ok", **schedule})
    except Exception as e:
        logger.exception("Surveillance error")
        return jsonify({"error": str(e)}), 500


# -------------------------
# Clinical Trials Route
# -------------------------
@app.route("/api/clinical_trials", methods=["GET"])
@require_auth
def api_clinical_trials():
    """Search ClinicalTrials.gov for trials matching patient profile."""
    try:
        user_id = request.user["user_id"]
        max_results = request.args.get("limit", 5, type=int)

        # Travel radius (miles): 25 / 50 / 100, or nationwide. Defaults to 100.
        radius_raw = (request.args.get("radius", "100") or "100").strip().lower()
        if radius_raw in ("nationwide", "none", "national", ""):
            radius_miles = None
        else:
            try:
                radius_miles = int(radius_raw)
            except (ValueError, TypeError):
                radius_miles = 100
            if radius_miles not in (25, 50, 100):
                radius_miles = 100

        # Load patient profile from Supabase
        profile = load_profile(user_id)
        if not profile:
            return jsonify({
                "error": "No patient profile found. Please build your profile first.",
                "trials": []
            }), 400

        # Extract patient context
        patient_context = extract_patient_context_complex(profile)
        # Inject cancer_slug so build_search_query consults the right
        # ClinicalTrials.gov condition synonyms instead of the legacy
        # unconditional "colorectal cancer" default.
        patient_context['cancer_slug'] = _resolve_cancer_slug(user_id, profile)

        # Validate profile readiness for trial search
        readiness = validate_trial_search_readiness(patient_context)
        if not readiness["ready"]:
            return jsonify({
                "error": readiness["prompt_message"],
                "missing_critical": readiness["missing_critical"],
                "missing_helpful": readiness["missing_helpful"],
                "just_in_time_question": readiness.get("just_in_time_question"),
                "chat_prefill": readiness.get("chat_prefill"),
                "trials": []
            }), 400

        # Search for clinical trials. Graph-aware ranking (Push 3): the
        # Modeler's per-patient graph adjusts ordering + rationale when active.
        from modeler import modeler_active
        trial_connections = profile.get("connections") if modeler_active() else None
        results = search_trials_for_patient(patient_context, max_results=max_results,
                                            radius_miles=radius_miles,
                                            connections=trial_connections)

        if results.get("error"):
            return jsonify({
                "status": "error",
                "error": results.get("error_message", "Error searching for trials"),
                "trials": []
            }), 200  # Still 200 since it's a valid response

        # Per-radius recruiting totals for the summary line (only when asked —
        # it's 4 extra cheap count queries; the chat path never requests them).
        radius_counts = count_trials_for_radii(patient_context) if request.args.get("counts") else None

        _emit_trials_shown(user_id, "api", results)

        return jsonify({
            "status": "ok",
            "trials": results["trials"],
            "total_found": results["total_found"],
            "radius_miles": results.get("radius_miles"),
            "relaxed_location": results.get("relaxed_location", False),
            "radius_counts": radius_counts,
            "search_criteria": {
                "condition": results["search_criteria"].get("query.cond"),
                "location": patient_context.get("zip_code"),
                "radius_miles": results.get("radius_miles"),
                "study_type": "INTERVENTIONAL",
                "biomarkers": patient_context.get("biomarkers"),
            }
        })

    except Exception as e:
        logger.exception("clinical_trials error")
        return jsonify({"error": str(e), "trials": []}), 500


# =============================================================================
# PITCH FEATURES (May 2026)
#   F2: /api/previsit_questions  — Pre-visit Question Generator
#   F3: /api/visit_recap         — Appointment Companion
#   F4: /api/insurance_appeal    — Insurance Appeal Letter Drafting
#   F5: /api/deep_research       — Deep-Dive Research Mode
# Each gated by FEATURE_<NAME> env var (defaults true).
# =============================================================================

@app.route("/api/previsit_questions", methods=["POST"])
@require_auth
def api_previsit_questions():
    """
    Generate a tailored list of pre-visit questions for a patient's next
    oncology appointment, grouped by topic. Cached 5 min per (user, context).
    """
    if not feature_enabled('pre_visit_questions'):
        return jsonify({"status": "feature_disabled"}), 503
    try:
        user_id = request.user["user_id"]

        # Rate limit: 10 generations per 60s per user
        from rate_limit import check_rate_limit
        allowed, _ = check_rate_limit(user_id, 'previsit_questions', *RATE_LIMIT_PREVISIT)
        if not allowed:
            return jsonify({"error": "Too many requests. Please wait a moment and try again."}), 429

        data = request.get_json(silent=True) or {}
        context = (data.get('context') or '').strip()
        if len(context) > 1000:
            context = context[:1000]

        # Load profile and build patient_summary
        patient_profile = load_profile(user_id) or {}
        patient_context = extract_patient_context_complex(patient_profile) if patient_profile else {}
        patient_summary = format_patient_summary_complex(patient_context) if patient_context else ""
        try:
            from profile_validator import derive_universal_core as _derive_core
            _pv_slug = _derive_core(patient_profile or {}).get('cancer_slug')
        except Exception:
            _pv_slug = None

        # Cache check
        from llm_utils import get_cached_previsit, set_cached_previsit, generate_previsit_questions
        cached = get_cached_previsit(user_id, context)
        if cached:
            return jsonify({
                "status": "ok",
                "groups": cached.get('groups', []),
                "used_fallback": cached.get('used_fallback', False),
                "cached": True,
                "saved": False,
            })

        # Generate
        result = generate_previsit_questions(patient_summary, context, cancer_slug=_pv_slug)
        set_cached_previsit(user_id, context, result)

        # Persist to profile (max 10 entries, drop oldest)
        saved = False
        try:
            existing = patient_profile.get('previsit_questions') or []
            if not isinstance(existing, list):
                existing = []
            entry = {
                "timestamp": datetime.now().isoformat(),
                "context": context,
                "groups": result['groups'],
                "used_fallback": result['used_fallback'],
            }
            existing.append(entry)
            if len(existing) > 10:
                existing = existing[-10:]
            patient_profile['previsit_questions'] = existing
            saved = save_profile(user_id, patient_profile)
        except Exception as e:
            logger.error(f"Failed to save previsit_questions to profile: {e}")

        return jsonify({
            "status": "ok",
            "groups": result['groups'],
            "used_fallback": result['used_fallback'],
            "cached": False,
            "saved": saved,
        })

    except Exception as e:
        logger.exception("previsit_questions error")
        return jsonify({"error": "Could not generate questions right now."}), 500


@app.route("/api/visit_recap", methods=["POST"])
@require_auth
def api_visit_recap():
    """
    Generate a structured recap from a patient's freeform visit notes.
    Detects contradictions vs. stored profile and saves to profile.visit_recaps.
    """
    if not feature_enabled('appointment_companion'):
        return jsonify({"status": "feature_disabled"}), 503
    try:
        user_id = request.user["user_id"]

        from rate_limit import check_rate_limit
        allowed, _ = check_rate_limit(user_id, 'visit_recap', *RATE_LIMIT_VISIT_RECAP)
        if not allowed:
            return jsonify({"error": "Too many requests. Please wait a moment and try again."}), 429

        data = request.get_json(silent=True) or {}
        transcript = (data.get('transcript') or '').strip()

        if len(transcript) < 50:
            return jsonify({"error": "Please share at least a few sentences about your visit so I can build a useful recap."}), 400

        truncated = False
        if len(transcript) > 8000:
            transcript = transcript[:8000]
            truncated = True

        # Sanitize PII from transcript before sending to LLM
        try:
            transcript_for_llm, _pii_warnings = sanitize_query(transcript)
        except Exception:
            transcript_for_llm = transcript

        patient_profile = load_profile(user_id) or {}
        patient_context = extract_patient_context_complex(patient_profile) if patient_profile else {}
        patient_summary = format_patient_summary_complex(patient_context) if patient_context else ""
        try:
            from profile_validator import derive_universal_core as _derive_core
            _vr_slug = _derive_core(patient_profile or {}).get('cancer_slug')
        except Exception:
            _vr_slug = None

        from llm_utils import generate_visit_recap
        recap = generate_visit_recap(patient_summary, transcript_for_llm, cancer_slug=_vr_slug)

        # Save to profile (max 20 entries, drop oldest)
        saved = False
        try:
            existing = patient_profile.get('visit_recaps') or []
            if not isinstance(existing, list):
                existing = []
            preview = transcript[:200] + ('...' if len(transcript) > 200 else '')
            entry = {
                "timestamp": datetime.now().isoformat(),
                "transcript_preview": preview,
                "recap": {
                    "discussed": recap['discussed'],
                    "treatment_changes": recap['treatment_changes'],
                    "action_items": recap['action_items'],
                    "follow_up_questions": recap['follow_up_questions'],
                    "flags": recap['flags'],
                },
                "used_fallback": recap['used_fallback'],
            }
            existing.append(entry)
            if len(existing) > 20:
                existing = existing[-20:]
            patient_profile['visit_recaps'] = existing
            saved = save_profile(user_id, patient_profile)
            # Mirror into the patient timeline (profile array stays authoritative
            # for the recap UI; patient_events is the longitudinal record).
            if saved:
                from supabase_storage import append_patient_event
                append_patient_event(user_id, 'visit_recap', payload={
                    "treatment_changes": recap['treatment_changes'],
                    "action_items_count": len(recap['action_items'] or []),
                    "flags": recap['flags'],
                }, source='visit_recap')
        except Exception as e:
            logger.error(f"Failed to save visit recap to profile: {e}")

        return jsonify({
            "status": "ok",
            "recap": recap,
            "saved": saved,
            "truncated": truncated,
        })

    except Exception as e:
        logger.exception("visit_recap error")
        return jsonify({"error": "Could not generate a recap right now."}), 500


@app.route("/api/insurance_appeal", methods=["POST"])
@require_auth
def api_insurance_appeal():
    """
    Accept a denial-letter PDF (multipart) OR typed denial text (form field
    'denial_text') and produce a drafted appeal letter grounded in NCCN/ASCO
    guidelines. Saves draft to profile.appeal_drafts.
    """
    if not feature_enabled('insurance_appeal'):
        return jsonify({"status": "feature_disabled"}), 503
    try:
        user_id = request.user["user_id"]

        from rate_limit import check_rate_limit
        allowed, _ = check_rate_limit(user_id, 'insurance_appeal', *RATE_LIMIT_APPEAL)
        if not allowed:
            return jsonify({"error": "Too many requests. Please wait a moment and try again."}), 429

        # Accept either a typed denial reason (form field) or a PDF upload.
        denial_text = (request.form.get('denial_text') or '').strip()
        pdf_file = request.files.get('denial_pdf')

        if pdf_file:
            # Validate filetype + extension
            filename = (pdf_file.filename or '').lower()
            if not filename.endswith('.pdf'):
                return jsonify({"error": "Only PDF files are accepted."}), 400
            mimetype = (pdf_file.mimetype or '').lower()
            if mimetype and mimetype not in ('application/pdf', 'application/x-pdf', 'application/octet-stream'):
                return jsonify({"error": "File doesn't appear to be a PDF."}), 400

            # Save to /tmp and extract
            import tempfile
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, dir='/tmp') as tf:
                    pdf_file.save(tf.name)
                    tmp_path = tf.name
                from pdf_utils import extract_text
                extracted = extract_text(tmp_path) or ''
            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            if len(extracted.strip()) < 100:
                return jsonify({
                    "error": "I couldn't extract readable text from this PDF. It may be image-only (scanned) or password-protected. Please type the denial reason in the text box instead."
                }), 422
            denial_text = extracted

        if not denial_text or len(denial_text.strip()) < 50:
            return jsonify({"error": "Please describe the denial reason or upload your denial letter PDF."}), 400

        # PII de-identify before LLM call (HIPAA-adjacent safety)
        try:
            denial_for_llm, _pii_warnings = sanitize_query(denial_text)
        except Exception:
            denial_for_llm = denial_text

        # Truncate the input we pass to the LLM
        denial_for_llm = denial_for_llm[:4000]

        # Load patient profile, build summary
        patient_profile = load_profile(user_id) or {}
        patient_context = extract_patient_context_complex(patient_profile) if patient_profile else {}
        patient_summary = format_patient_summary_complex(patient_context) if patient_context else ""

        try:
            from profile_validator import derive_universal_core as _derive_core
            _appeal_slug = _derive_core(patient_profile or {}).get('cancer_slug')
        except Exception:
            _appeal_slug = None
        _appeal_filter = [_appeal_slug, 'general'] if _appeal_slug else None

        # Retrieve relevant guidelines using denial reason as query
        retrieved = []
        guidelines_formatted = ""
        try:
            chunks = load_all_chunks()
            if chunks:
                # Use first 1000 chars of denial text as retrieval query
                retrieval_query = denial_for_llm[:1000]
                retrieved = hybrid_search(retrieval_query, chunks, top_k=5, cancer_types=_appeal_filter) or []
                from llm_utils import select_chunks_within_budget
                guidelines_formatted = select_chunks_within_budget(retrieved, 2000)
        except Exception as e:
            logger.warning(f"Guideline retrieval failed for appeal: {e}")

        # Generate appeal letter (with inline citations)
        from llm_utils import generate_insurance_appeal
        result = generate_insurance_appeal(patient_summary, denial_for_llm, retrieved, guidelines_formatted, cancer_slug=_appeal_slug)

        if result['used_fallback']:
            return jsonify({
                "status": "error",
                "error": result.get('error', 'Could not draft a letter right now.'),
            }), 500

        # Build sources_metadata for the bottom panel (mirrors /api/chat)
        sources_metadata = []
        try:
            seen = set()
            for chunk in retrieved[:5]:
                if isinstance(chunk, dict) and chunk.get('filename'):
                    fname = chunk['filename']
                    if fname in seen:
                        continue
                    seen.add(fname)
                    content = chunk.get('content', '') or ''
                    preview = content[:140].strip()
                    if len(content) > 140:
                        preview += '...'
                    sources_metadata.append({
                        "title": fname,
                        "section": chunk.get('chunk_index'),
                        "preview": preview,
                    })
        except Exception:
            pass

        # Save to profile (max 10 entries)
        saved = False
        try:
            existing = patient_profile.get('appeal_drafts') or []
            if not isinstance(existing, list):
                existing = []
            denial_preview = denial_text[:200] + ('...' if len(denial_text) > 200 else '')
            entry = {
                "timestamp": datetime.now().isoformat(),
                "denial_preview": denial_preview,
                "draft": result['draft'],
                "citations": result['citations'],
                "sources": sources_metadata,
            }
            existing.append(entry)
            if len(existing) > 10:
                existing = existing[-10:]
            patient_profile['appeal_drafts'] = existing
            saved = save_profile(user_id, patient_profile)
        except Exception as e:
            logger.error(f"Failed to save appeal draft: {e}")

        return jsonify({
            "status": "ok",
            "draft": result['draft'],
            "citations": result['citations'],
            "sources": sources_metadata,
            "saved": saved,
        })

    except Exception as e:
        logger.exception("insurance_appeal error")
        return jsonify({"error": "Could not draft an appeal letter right now."}), 500


@app.route("/api/deep_research", methods=["POST"])
@require_auth
def api_deep_research():
    """
    Long-running research endpoint: multi-pass retrieval + longer LLM call +
    verification. ~15–45s. Off-topic queries refused immediately.
    """
    if not feature_enabled('deep_dive'):
        return jsonify({"status": "feature_disabled"}), 503
    import time as _t
    start_ts = _t.time()

    try:
        user_id = request.user["user_id"]

        from rate_limit import check_rate_limit
        # Heavy endpoint: 3 requests per 5 minutes per user
        allowed, _ = check_rate_limit(user_id, 'deep_research', *RATE_LIMIT_DEEP_RESEARCH)
        if not allowed:
            return jsonify({"error": "Deep research is rate-limited to 3 requests per 5 minutes. Please try again shortly."}), 429

        data = request.get_json(silent=True) or {}
        query = (data.get('query') or '').strip()
        if len(query) < 8:
            return jsonify({"error": "Please ask a more detailed question for deep research."}), 400
        if len(query) > 1000:
            query = query[:1000]

        # Derive cancer slug for retrieval filter + LLM overlay.
        try:
            from profile_validator import derive_universal_core as _derive_core
            _dr_profile = load_profile(user_id) or {}
            _dr_slug = _derive_core(_dr_profile).get('cancer_slug')
        except Exception:
            _dr_slug = None
        _dr_filter = [_dr_slug, 'general'] if _dr_slug else None

        # Off-topic guard (reuse hallucination-mitigation infra)
        try:
            from confidence import is_in_oncology_domain, render_off_topic_response
            chunks = load_all_chunks()
            quick_retrieved = hybrid_search(query, chunks, top_k=5, cancer_types=_dr_filter) if chunks else []
            on_topic, _reason = is_in_oncology_domain(query, quick_retrieved)
            if not on_topic:
                _ot_text = render_off_topic_response(_dr_slug)
                return jsonify({
                    "status": "off_topic",
                    "report": _ot_text,
                    "sections": [{"title": "Outside scope", "body": _ot_text}],
                    "citations": {},
                    "sources": [],
                    "verified": True,
                    "took_seconds": round(_t.time() - start_ts, 1),
                })
        except Exception as e:
            logger.warning(f"Off-topic check failed in deep_research: {e}")
            chunks = load_all_chunks()
            quick_retrieved = []

        # Multi-pass retrieval
        from llm_utils import derive_subqueries, select_chunks_within_budget, generate_deep_research
        retrieved = list(quick_retrieved)
        seen_ids = set()
        for c in retrieved:
            if isinstance(c, dict):
                seen_ids.add((c.get('document_id'), c.get('chunk_index')))

        # Pass 1: broaden top_k for the primary query
        try:
            primary = hybrid_search(query, chunks, top_k=12, cancer_types=_dr_filter) or []
            for c in primary:
                if isinstance(c, dict):
                    key = (c.get('document_id'), c.get('chunk_index'))
                    if key not in seen_ids:
                        seen_ids.add(key)
                        retrieved.append(c)
        except Exception as e:
            logger.warning(f"Deep research primary retrieval failed: {e}")

        # Pass 2: derive 2-3 sub-queries and search each
        subqueries = []
        try:
            subqueries = derive_subqueries(query) or []
            for sq in subqueries:
                try:
                    extra = hybrid_search(sq, chunks, top_k=4, cancer_types=_dr_filter) or []
                    for c in extra:
                        if isinstance(c, dict):
                            key = (c.get('document_id'), c.get('chunk_index'))
                            if key not in seen_ids:
                                seen_ids.add(key)
                                retrieved.append(c)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Deep research sub-query retrieval failed: {e}")

        # Cap total chunks fed to LLM (prevents runaway prompt)
        retrieved = retrieved[:20]

        # Patient context
        patient_profile = load_profile(user_id) or {}
        patient_context = extract_patient_context_complex(patient_profile) if patient_profile else {}
        patient_summary = format_patient_summary_complex(patient_context) if patient_context else ""

        # Generate report
        result = generate_deep_research(query, retrieved, patient_summary, cancer_slug=_dr_slug)

        if result.get('used_fallback'):
            from verify import HEDGED_FALLBACK_RESPONSE
            return jsonify({
                "status": "fallback",
                "report": HEDGED_FALLBACK_RESPONSE,
                "sections": [{"title": "I'm not confident enough to answer this", "body": HEDGED_FALLBACK_RESPONSE}],
                "citations": {},
                "sources": [],
                "verified": False,
                "took_seconds": round(_t.time() - start_ts, 1),
            })

        # Source metadata for the bottom panel
        sources_metadata = []
        try:
            seen = set()
            for chunk in retrieved[:8]:
                if isinstance(chunk, dict) and chunk.get('filename'):
                    fname = chunk['filename']
                    if fname in seen:
                        continue
                    seen.add(fname)
                    content = chunk.get('content', '') or ''
                    preview = content[:140].strip()
                    if len(content) > 140:
                        preview += '...'
                    sources_metadata.append({
                        "title": fname,
                        "section": chunk.get('chunk_index'),
                        "preview": preview,
                    })
        except Exception:
            pass

        took = round(_t.time() - start_ts, 1)
        return jsonify({
            "status": "ok",
            "report": result['report'],
            "sections": result['sections'],
            "citations": result['citations'],
            "sources": sources_metadata,
            "verified": result.get('verified', True),
            "fabrication_risk": result.get('fabrication_risk', 'unknown'),
            "subqueries_used": subqueries,
            "took_seconds": took,
        })

    except Exception as e:
        logger.exception("deep_research error")
        return jsonify({"error": "Deep research failed. Try a more specific question."}), 500


# =============================================================================
# PRIVACY APPEALS (MHMDA / state privacy laws — 45-day SLA)
# =============================================================================

ALLOWED_APPEAL_TYPES = {"access", "deletion", "consent_withdrawal", "other"}

@app.route("/api/privacy_appeal", methods=["POST"])
@require_auth
def api_privacy_appeal():
    """
    Submit a privacy appeal for a denied access / deletion / consent withdrawal
    request. Persists to patient_profiles.raw_profile.privacy_appeals[].
    45-day SLA (extendable by 45 more days where reasonably necessary).
    """
    try:
        from datetime import timedelta
        user_id = request.user["user_id"]

        from rate_limit import check_rate_limit
        allowed, _ = check_rate_limit(user_id, 'privacy_appeal', *RATE_LIMIT_PRIVACY_APPEAL)
        if not allowed:
            return jsonify({"error": "You've submitted the maximum number of appeals in 24 hours. Please email appeals@wondrlinkfoundation.org for urgent matters."}), 429

        data = request.get_json(silent=True) or {}
        req_type = (data.get('request_type') or '').strip().lower()
        reason = (data.get('reason') or '').strip()

        if req_type not in ALLOWED_APPEAL_TYPES:
            return jsonify({"error": "Please choose a valid request type."}), 400
        if len(reason) < 10:
            return jsonify({"error": "Please describe your request in at least one sentence."}), 400
        if len(reason) > 2000:
            reason = reason[:2000]

        now = datetime.now()
        sla_due = (now + timedelta(days=45)).isoformat()
        appeal_id = f"appeal-{int(now.timestamp())}"
        entry = {
            "appeal_id": appeal_id,
            "timestamp": now.isoformat(),
            "request_type": req_type,
            "reason": reason,
            "status": "submitted",
            "sla_due": sla_due,
            "resolved_at": None,
            "resolution_note": None,
        }

        # Append to profile.privacy_appeals
        patient_profile = load_profile(user_id) or {}
        existing = patient_profile.get('privacy_appeals') or []
        if not isinstance(existing, list):
            existing = []
        existing.append(entry)
        if len(existing) > 20:
            existing = existing[-20:]
        patient_profile['privacy_appeals'] = existing
        save_profile(user_id, patient_profile)

        # Structured log for ops awareness (no PII beyond appeal_id + user_id)
        logger.info(f"PRIVACY_APPEAL submitted: appeal_id={appeal_id} user_id={user_id} type={req_type} sla_due={sla_due}")

        return jsonify({
            "status": "ok",
            "appeal_id": appeal_id,
            "sla_due": sla_due,
            "message": "Your appeal has been recorded. We will respond within 45 days.",
        })
    except Exception as e:
        logger.exception("privacy_appeal error")
        return jsonify({"error": "Could not record your appeal right now."}), 500


@app.route("/api/hero", methods=["GET"])
@require_auth
def api_hero():
    """
    Return personalized hero-card data for the chat welcome surface.

    Response shape:
      {
        "has_profile": bool,
        "first_name": str | "",
        "phase_description": str,          # "You're 14 days into FOLFOX, cycle 2."
        "regimen": str | "",
        "days_into": int | null,
        "cycle": int | null,
        "last_visit": { when, when_pretty, pending_followups, changed_treatment } | null,
        "suggestions": [str, str, str]
      }
    """
    try:
        user_id = request.user["user_id"]
        profile = load_profile(user_id) or {}
        if not profile:
            return jsonify({"has_profile": False})

        ctx = extract_patient_context_complex(profile)
        try:
            from profile_validator import derive_universal_core as _derive_core
            _hero_slug = _derive_core(profile or {}).get('cancer_slug')
        except Exception:
            _hero_slug = None

        from hero import (
            compute_days_into_treatment,
            describe_phase,
            format_visit_summary,
            suggest_starter_questions,
        )

        first_name = (profile.get("patient") or {}).get("firstName") or \
                     (profile.get("patient") or {}).get("name", "").split(" ")[0] or ""

        recaps = profile.get("visit_recaps") or []
        last_recap = recaps[-1] if (isinstance(recaps, list) and recaps) else None

        return jsonify({
            "has_profile": True,
            "first_name": first_name,
            "phase_description": describe_phase(profile, ctx, cancer_slug=_hero_slug),
            "regimen": ctx.get("current_regimen") or "",
            "days_into": compute_days_into_treatment(profile),
            "cycle": ctx.get("current_cycle_number"),
            "last_visit": format_visit_summary(last_recap),
            "suggestions": suggest_starter_questions(profile, ctx, cancer_slug=_hero_slug),
            "cancer_slug": _hero_slug or "colorectal",
        })
    except Exception as e:
        logger.exception("hero error")
        return jsonify({"has_profile": False, "error": str(e)}), 200


@app.route("/api/care_snapshot", methods=["GET"])
@require_auth
def api_care_snapshot():
    """
    Compact longitudinal data for the Care Snapshot card at the top of the
    sidebar. Bundles PHQ-9 trend, days since last symptom check-in, and a
    coarse trend label into a single response.
    """
    try:
        from supabase_storage import load_all_screening_history
        user_id = request.user["user_id"]
        history = load_all_screening_history(user_id) or {}

        # PHQ-9: last 6 entries, oldest first
        phq9 = (history.get("PHQ9") or [])[-6:]
        phq9_points = []
        for entry in phq9:
            score = entry.get("total_score")
            ts = entry.get("completed_at")
            if score is not None:
                phq9_points.append({"score": score, "completed_at": ts})

        # Days since last symptom check-in
        symptom = history.get("SYMPTOM") or []
        days_since_symptom = None
        if symptom:
            last_ts = symptom[-1].get("completed_at")
            if last_ts:
                try:
                    s = last_ts.replace("Z", "").split("+")[0].split(".")[0]
                    last_dt = datetime.fromisoformat(s)
                    days_since_symptom = max(0, (datetime.utcnow() - last_dt).days)
                except Exception:
                    pass

        # Coarse PHQ-9 trend: look at the most-recent 3 points if available
        trend = "none"
        if len(phq9_points) >= 2:
            scores = [p["score"] for p in phq9_points[-3:]]
            if all(scores[i] > scores[i + 1] for i in range(len(scores) - 1)):
                trend = "improving"
            elif all(scores[i] < scores[i + 1] for i in range(len(scores) - 1)):
                trend = "worsening"
            else:
                trend = "stable"

        # Multi-cancer: surface the user's next surveillance milestone for
        # their selected cancer. Pulled from config/cancers/<slug>/surveillance.yaml.
        # First milestone in the YAML wins for the snapshot pill.
        next_milestone = None
        try:
            from supabase_storage import get_cancer_slug
            from cancer_registry import load_surveillance, display_name
            slug = get_cancer_slug(user_id) or 'colorectal'
            rubric = load_surveillance(slug) or {}
            milestones = rubric.get('milestones') or []
            if milestones:
                m = milestones[0]
                next_milestone = {
                    "cancer_slug": slug,
                    "cancer_display": display_name(slug),
                    "test": m.get('test') or m.get('id') or 'Check-in',
                    "cadence": m.get('cadence') or '',
                    "rationale": m.get('rationale') or '',
                }
        except Exception as _e:
            logger.warning("next_milestone unavailable: %s", _e)

        return jsonify({
            "phq9_points": phq9_points,
            "days_since_symptom": days_since_symptom,
            "phq9_trend": trend,
            "phq9_count": len(phq9_points),
            "next_milestone": next_milestone,
        })
    except Exception as e:
        logger.exception("care_snapshot error")
        return jsonify({"phq9_points": [], "days_since_symptom": None, "phq9_trend": "none", "phq9_count": 0, "next_milestone": None}), 200


# -------------------------
# -------------------------
# Account Deletion (GDPR/CCPA)
# -------------------------
@app.route("/api/delete_account", methods=["DELETE"])
@require_auth
def api_delete_account():
    """Delete all user data and account. GDPR Article 17 compliance."""
    try:
        user_id = request.user["user_id"]

        # Delete all data from all tables
        from supabase_storage import delete_all_user_data
        results = delete_all_user_data(user_id)

        # Delete the auth user account
        try:
            from supabase_client import get_admin_client
            admin = get_admin_client()
            admin.auth.admin.delete_user(user_id)
            results['auth_user'] = 'deleted'
        except Exception as e:
            results['auth_user'] = f'error: {str(e)}'

        logger.info(f"Account deleted for user {user_id}")
        return jsonify({"status": "ok", "message": "Account and all data permanently deleted", "details": results})
    except Exception as e:
        logger.exception("Account deletion error")
        return jsonify({"error": str(e)}), 500


# -------------------------
# Health Check
# -------------------------
@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "wondrlink-api"})

# -------------------------
# CORS
# -------------------------
@app.route("/api/<path:path>", methods=["OPTIONS"])
def handle_options(path):
    return ("", 200)

@app.after_request
def apply_cors(response):
    origin = request.headers.get("Origin")
    if _origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return response

# -------------------------
# For local development
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
