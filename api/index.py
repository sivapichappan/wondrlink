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
    save_chat_message, load_chat_history, clear_chat_history
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
    validate_trial_search_readiness
)

# -------------------------
# Config & Globals
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wondr-api")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5000").split(",")


def feature_enabled(flag_name: str) -> bool:
    """Per-feature kill switch via env var FEATURE_<NAME>. Defaults to True."""
    return os.getenv(f"FEATURE_{flag_name.upper()}", "true").lower() == "true"


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
# Auth Routes
# -------------------------
@app.route("/api/auth/register", methods=["POST"])
def api_register():
    """Register a new user with Supabase Auth."""
    try:
        # Rate limit registration by IP
        from rate_limit import check_rate_limit
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        allowed, remaining = check_rate_limit(client_ip, 'auth/register', 3, 60)
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

        logger.info(f"New user registered: {email}")
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
        allowed, remaining = check_rate_limit(client_ip, 'auth/login', 5, 15)
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

        logger.info(f"User logged in: {email}")
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
            return jsonify({
                "profile": profile,
                "patient_summary": patient_summary,
                "context": patient_context
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
        user_id = request.user["user_id"]
        state = check_acknowledgement(user_id)
        acknowledged = state.get('acknowledged', False)
        version = state.get('consent_version')
        # User needs to re-consent if they've never acknowledged, OR if their
        # accepted version is below current.
        needs_consent = (not acknowledged) or (version != CURRENT_CONSENT_VERSION)
        return jsonify({
            "acknowledged": acknowledged,
            "consent_version": version,
            "current_version": CURRENT_CONSENT_VERSION,
            "needs_consent": needs_consent,
            "state_restricted": state.get('state_restricted', False),
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
            build_consent_metadata, CURRENT_CONSENT_VERSION,
        )
        user_id = request.user["user_id"]
        payload = request.get_json(silent=True) or {}

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

        # Build the audit record and persist
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
        metadata = build_consent_metadata(payload, ip_address=client_ip)
        success = save_acknowledgement(
            user_id,
            consent_metadata=metadata,
            consent_version=CURRENT_CONSENT_VERSION,
        )
        if not success:
            return jsonify({"error": "Failed to save acknowledgement"}), 500

        return jsonify({
            "status": "ok",
            "message": "Acknowledgement saved",
            "consent_version": CURRENT_CONSENT_VERSION,
        })
    except Exception as e:
        logger.exception("save_acknowledgement error")
        return jsonify({"error": str(e)}), 500


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
        allowed, remaining = check_rate_limit(user_id, 'chat', 30, 60)
        if not allowed:
            return jsonify({"error": "You've reached the message limit. Please wait a bit before sending more."}), 429
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

        # Load chunks from Supabase
        indexed_chunks = load_all_chunks()

        # Get conversation history from Supabase
        history = get_conversation_history(session_id)
        conversation_context = format_conversation_context(history)

        # Load patient profile from Supabase
        patient_profile = load_profile(user_id)
        # load_profile returns {} if not found, which is falsy in Python. 
        # We want to ensure extract_patient_context_complex is called even if profile is mostly empty.
        patient_context = extract_patient_context_complex(patient_profile) if (patient_profile is not None and len(patient_profile) > 0) else {}

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

        # Classify query type early so we can adjust chunk retrieval
        query_type = classify_query_type(message)
        effective_top_k = 8 if query_type in ('treatment', 'clinical_trial') else 5

        # Search relevant chunks (hybrid: TF + vector with RRF)
        retrieved = []
        try:
            retrieved = hybrid_search(message, indexed_chunks, top_k=effective_top_k)
            logger.info(f"hybrid_search returned {len(retrieved)} chunks (top_k={effective_top_k}, query_type={query_type})")
        except Exception:
            logger.exception("hybrid_search failed, falling back to TF-only")
            try:
                retrieved = search_chunks(message, indexed_chunks, top_k=effective_top_k)
            except Exception:
                logger.exception("search_chunks also failed")

        # Off-topic detection — refuse with redirect if query is outside scope
        try:
            from confidence import is_on_topic, OFF_TOPIC_RESPONSE
            on_topic, ot_reason = is_on_topic(message, retrieved)
            if not on_topic:
                logger.info(f"Off-topic query refused: {ot_reason}")
                return jsonify({
                    "status": "ok",
                    "answer": OFF_TOPIC_RESPONSE,
                    "api_used": "off-topic-filter",
                    "retrieved_count": 0,
                    "off_topic": True,
                    "sources": [],
                    "guidelines_used": [],
                    "has_guidelines": False,
                })
        except Exception:
            logger.exception("Off-topic detection failed (continuing with normal flow)")

        # Assemble prompt
        if mismatch_detected:
            message_with_note = f"{message}\n\n[SYSTEM NOTE: User asked about different cancer type than their profile]"
            prompt, prompt_metadata = assemble_prompt(message_with_note, retrieved, patient_profile, response_length,
                                    conversation_context, patient_context)
        else:
            prompt, prompt_metadata = assemble_prompt(message, retrieved, patient_profile, response_length,
                                    conversation_context, patient_context)

        # Check LLM availability
        llm_status = get_llm_status()
        if not llm_status["primary_api"]:
            return jsonify({
                "error": "No LLM API available. Please check TOGETHER_API_KEY or GROQ_API_KEY.",
                "debug_info": llm_status
            }), 500

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

            # Add relevant patient resources (unless brief response)
            if response_length != "brief":
                resources_text = get_relevant_resources(query_type, include_resources=True, query=message)
                if resources_text:
                    final_answer = final_answer + resources_text

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
                            "missing_helpful": readiness["missing_helpful"]
                        }
                    else:
                        trials_result = search_trials_for_patient(patient_context, max_results=5)
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
                        elif trials_result.get("error") == "no_zip_code":
                            clinical_trials_data = {
                                "error": "no_zip_code",
                                "message": "To search for clinical trials near you, please add your zip code to your profile."
                            }
                except Exception as e:
                    logger.error(f"Error searching clinical trials: {e}", exc_info=True)

            # Store conversation in Supabase (store original answer without resources for cleaner history)
            add_conversation(session_id, user_id, message, answer)

            # --- Feature 1: Scan for profile updates ---
            profile_updates = {}
            update_success = False
            try:
                profile_updates = extract_profile_updates_from_query(original_message, patient_profile or {})
                if profile_updates:
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

            # Extract sources for the frontend panel
            sources_metadata = []
            guidelines_used = []
            guideline_keywords = ['NCCN', 'guideline', 'ACS', 'ASCO', 'CDC', 'NCI', 'recommendation']
            try:
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
                "guidelines_used": guidelines_used,
                "has_guidelines": len(guidelines_used) > 0,
                "clinical_trials": clinical_trials_data,
                "urgency": {
                    "detected": prompt_metadata.get('urgency_detected', False),
                    "level": prompt_metadata.get('urgency_level'),
                    "guidance": prompt_metadata.get('urgency_guidance', '')
                } if prompt_metadata.get('urgency_detected') else None,
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

        instrument = data.get('instrument')  # PHQ9, GAD7, PSS10, ISI
        scores = data.get('scores', {})
        total_score = data.get('total_score')
        severity_label = data.get('severity_label', '')

        if not instrument or total_score is None:
            return jsonify({"error": "instrument and total_score required"}), 400

        valid_instruments = ['PHQ9', 'GAD7', 'PSS10', 'ISI']
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

        from surveillance import generate_surveillance_schedule
        schedule = generate_surveillance_schedule(stage, surgery_date,
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

        # Load patient profile from Supabase
        profile = load_profile(user_id)
        if not profile:
            return jsonify({
                "error": "No patient profile found. Please build your profile first.",
                "trials": []
            }), 400

        # Extract patient context
        patient_context = extract_patient_context_complex(profile)

        # Validate profile readiness for trial search
        readiness = validate_trial_search_readiness(patient_context)
        if not readiness["ready"]:
            return jsonify({
                "error": readiness["prompt_message"],
                "missing_critical": readiness["missing_critical"],
                "missing_helpful": readiness["missing_helpful"],
                "trials": []
            }), 400

        # Search for clinical trials
        results = search_trials_for_patient(patient_context, max_results=max_results)

        if results.get("error"):
            return jsonify({
                "status": "error",
                "error": results.get("error_message", "Error searching for trials"),
                "trials": []
            }), 200  # Still 200 since it's a valid response

        return jsonify({
            "status": "ok",
            "trials": results["trials"],
            "total_found": results["total_found"],
            "search_criteria": {
                "condition": results["search_criteria"].get("query.cond"),
                "location": patient_context.get("zip_code"),
                "biomarkers": patient_context.get("biomarkers"),
                "intervention": results["search_criteria"].get("query.intr")
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
        allowed, _ = check_rate_limit(user_id, 'previsit_questions', 10, 60)
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
        result = generate_previsit_questions(patient_summary, context)
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
        allowed, _ = check_rate_limit(user_id, 'visit_recap', 10, 60)
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

        from llm_utils import generate_visit_recap
        recap = generate_visit_recap(patient_summary, transcript_for_llm)

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
        allowed, _ = check_rate_limit(user_id, 'insurance_appeal', 5, 60)
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

        # Retrieve relevant guidelines using denial reason as query
        retrieved = []
        guidelines_formatted = ""
        try:
            chunks = load_all_chunks()
            if chunks:
                # Use first 1000 chars of denial text as retrieval query
                retrieval_query = denial_for_llm[:1000]
                retrieved = hybrid_search(retrieval_query, chunks, top_k=5) or []
                from llm_utils import select_chunks_within_budget
                guidelines_formatted = select_chunks_within_budget(retrieved, 2000)
        except Exception as e:
            logger.warning(f"Guideline retrieval failed for appeal: {e}")

        # Generate appeal letter (with inline citations)
        from llm_utils import generate_insurance_appeal
        result = generate_insurance_appeal(patient_summary, denial_for_llm, retrieved, guidelines_formatted)

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
        allowed, _ = check_rate_limit(user_id, 'deep_research', 3, 300)
        if not allowed:
            return jsonify({"error": "Deep research is rate-limited to 3 requests per 5 minutes. Please try again shortly."}), 429

        data = request.get_json(silent=True) or {}
        query = (data.get('query') or '').strip()
        if len(query) < 8:
            return jsonify({"error": "Please ask a more detailed question for deep research."}), 400
        if len(query) > 1000:
            query = query[:1000]

        # Off-topic guard (reuse hallucination-mitigation infra)
        try:
            from confidence import is_on_topic, OFF_TOPIC_RESPONSE
            chunks = load_all_chunks()
            quick_retrieved = hybrid_search(query, chunks, top_k=5) if chunks else []
            on_topic, _reason = is_on_topic(query, quick_retrieved)
            if not on_topic:
                return jsonify({
                    "status": "off_topic",
                    "report": OFF_TOPIC_RESPONSE,
                    "sections": [{"title": "Outside scope", "body": OFF_TOPIC_RESPONSE}],
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
            primary = hybrid_search(query, chunks, top_k=12) or []
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
                    extra = hybrid_search(sq, chunks, top_k=4) or []
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
        result = generate_deep_research(query, retrieved, patient_summary)

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
        allowed, _ = check_rate_limit(user_id, 'privacy_appeal', 3, 86400)
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
            "phase_description": describe_phase(profile, ctx),
            "regimen": ctx.get("current_regimen") or "",
            "days_into": compute_days_into_treatment(profile),
            "cycle": ctx.get("current_cycle_number"),
            "last_visit": format_visit_summary(last_recap),
            "suggestions": suggest_starter_questions(profile, ctx),
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

        return jsonify({
            "phq9_points": phq9_points,
            "days_since_symptom": days_since_symptom,
            "phq9_trend": trend,
            "phq9_count": len(phq9_points),
        })
    except Exception as e:
        logger.exception("care_snapshot error")
        return jsonify({"phq9_points": [], "days_since_symptom": None, "phq9_trend": "none", "phq9_count": 0}), 200


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
