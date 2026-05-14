# supabase_storage.py
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from supabase_client import get_supabase_client, get_admin_client

logger = logging.getLogger("supabase_storage")


# -------------------------
# Patient Profile Operations
# Uses patient_profiles table with raw_profile JSON column
# -------------------------

def save_profile(user_id: str, profile_data: dict) -> bool:
    """
    Save or update a patient profile for a user.

    During the multi-cancer dual-write window, this writes BOTH the legacy
    raw_profile + denormalized columns AND the v2 universal-core columns
    (cancer_slug, role, stage_group, treatment_intent, clinical). If the
    v2 columns don't exist yet (migration not applied), the write
    transparently falls back to the legacy row.

    Args:
        user_id: The user's UUID
        profile_data: The patient profile JSON data

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_admin_client()

        # Legacy denormalized columns (existing behavior — unchanged).
        patient = profile_data.get('patient', {})
        diagnosis = profile_data.get('primaryDiagnosis', {})
        profile_row = {
            'user_id': user_id,
            'raw_profile': profile_data,
            'patient_name': patient.get('name'),
            'date_of_birth': patient.get('dob'),
            'gender': patient.get('sex'),
            'ecog_score': patient.get('ecog'),
            'allergies': patient.get('allergies'),
            'comorbidities': patient.get('comorbidities'),
            'cancer_type': diagnosis.get('site'),
            'histology': diagnosis.get('histology'),
            'cancer_stage': diagnosis.get('stage'),
            'biomarkers': diagnosis.get('biomarkers', {}),
            'current_treatments': profile_data.get('treatments', []),
            'updated_at': datetime.now().isoformat()
        }

        # v2 universal-core columns + clinical JSONB payload.
        v2_row = None
        try:
            from lib.profile_validator import (
                derive_clinical_payload,
                derive_universal_core,
                validate_clinical,
            )
            core = derive_universal_core(profile_data)
            clinical_payload = derive_clinical_payload(profile_data)
            ok, errors = validate_clinical(core['cancer_slug'], clinical_payload)
            if not ok:
                logger.warning(
                    "Clinical payload validation failed for user %s (cancer=%s): %s",
                    user_id, core['cancer_slug'], '; '.join(errors[:3])
                )
                clinical_payload = {}
            v2_row = {
                **profile_row,
                **core,
                'clinical': clinical_payload,
                'schema_version': 'v2',
            }
        except Exception as e:
            logger.warning("v2 derivation failed for user %s: %s", user_id, e)

        try:
            client.table('patient_profiles').upsert(
                v2_row if v2_row is not None else profile_row,
                on_conflict='user_id'
            ).execute()
        except Exception as e:
            err_msg = str(e).lower()
            if v2_row is not None and ('column' in err_msg or 'does not exist' in err_msg):
                logger.warning(
                    "v2 columns missing — falling back to legacy row write "
                    "(apply supabase_migrations/2026_05_14_profile_v2.sql to enable v2): %s",
                    e,
                )
                client.table('patient_profiles').upsert(
                    profile_row,
                    on_conflict='user_id'
                ).execute()
            else:
                raise

        logger.info(f"Saved patient profile for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save profile for user {user_id}: {e}")
        logger.exception("Full traceback:")
        return False


def load_profile(user_id: str) -> dict:
    """
    Load a patient profile for a user.

    Args:
        user_id: The user's UUID

    Returns:
        Profile data dict (from raw_profile), or empty dict if not found
    """
    try:
        # Use admin client to bypass RLS - user_id is verified in API layer
        client = get_admin_client()
        result = client.table('patient_profiles') \
            .select('raw_profile') \
            .eq('user_id', user_id) \
            .single() \
            .execute()

        if result.data:
            logger.info(f"Loaded patient profile for user {user_id}")
            return result.data.get('raw_profile', {})
        return {}
    except Exception as e:
        # Single() throws if no rows found, which is expected
        if "0 rows" not in str(e).lower():
            logger.error(f"Failed to load profile: {e}")
        return {}


def get_cancer_slug(user_id: str) -> Optional[str]:
    """
    Resolve the user's cancer slug.

    Tries the v2 cancer_slug column first; on miss (or pre-migration), falls
    back to deriving it from raw_profile.primaryDiagnosis.site via the
    cancer_registry. Returns None when no profile exists.
    """
    try:
        client = get_admin_client()
        # Try v2 column first
        try:
            result = client.table('patient_profiles') \
                .select('cancer_slug, raw_profile') \
                .eq('user_id', user_id) \
                .single() \
                .execute()
            if result.data:
                slug = result.data.get('cancer_slug')
                if slug:
                    return slug
                raw = result.data.get('raw_profile') or {}
                site = (raw.get('primaryDiagnosis') or {}).get('site') or ''
                if site:
                    from lib.cancer_registry import resolve_slug
                    return resolve_slug(site)
        except Exception as e:
            # cancer_slug column may not exist yet (pre-migration); fall back
            if "0 rows" in str(e).lower():
                return None
            # Other errors → drop to legacy path
        # Legacy: read only raw_profile (works pre-migration)
        result = client.table('patient_profiles') \
            .select('raw_profile') \
            .eq('user_id', user_id) \
            .single() \
            .execute()
        if result.data:
            raw = result.data.get('raw_profile') or {}
            site = (raw.get('primaryDiagnosis') or {}).get('site') or ''
            if site:
                from lib.cancer_registry import resolve_slug
                return resolve_slug(site)
    except Exception as e:
        if "0 rows" not in str(e).lower():
            logger.error(f"get_cancer_slug failed for user {user_id}: {e}")
    return None


def clear_profile(user_id: str) -> bool:
    """
    Delete a patient profile for a user.

    Args:
        user_id: The user's UUID

    Returns:
        True if successful, False otherwise
    """
    try:
        # Use admin client to bypass RLS - user_id is verified in API layer
        client = get_admin_client()
        client.table('patient_profiles') \
            .delete() \
            .eq('user_id', user_id) \
            .execute()

        logger.info(f"Cleared patient profile for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear profile: {e}")
        return False


def merge_profile_updates(target: dict, updates: dict) -> dict:
    """Recursively merge updates into target profile."""
    for key, value in updates.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            merge_profile_updates(target[key], value)
        else:
            target[key] = value
    return target


def update_profile_with_sources(user_id: str, updates: dict, source_info: dict) -> bool:
    """
    Update patient profile with new data and track sources.

    source_info should look like: {"source_type": "chat", "session_id": "...", "timestamp": "..."}
    """
    if not updates:
        logger.debug(f"No updates to apply for user {user_id}")
        return True

    try:
        logger.info(f"Applying profile updates for user {user_id}: {list(updates.keys())}")
        current_profile = load_profile(user_id)
        logger.debug(f"Current profile has {len(current_profile)} keys")

        # Merge updates into current profile
        updated_profile = merge_profile_updates(current_profile, updates)

        # Handle field-specific sources
        # We'll store sources in a special '_sources' field within the profile
        if '_sources' not in updated_profile:
            updated_profile['_sources'] = {}

        def track_sources(data, path=""):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    track_sources(value, current_path)
                else:
                    updated_profile['_sources'][current_path] = source_info

        track_sources(updates)

        # Save the updated profile back
        result = save_profile(user_id, updated_profile)
        if result:
            logger.info(f"Profile update saved successfully for user {user_id}")
        else:
            logger.error(f"save_profile returned False for user {user_id} - check database schema")
        return result
    except Exception as e:
        logger.error(f"Failed to update profile with sources for user {user_id}: {e}")
        logger.exception("Full traceback:")
        return False


# -------------------------
# Document Chunk Operations
# -------------------------

def save_document_chunks(filename: str, chunks: List[str]) -> bool:
    """
    Save document chunks to the database.
    Uses admin client to bypass RLS since chunks are shared.

    Args:
        filename: The source document filename
        chunks: List of text chunks

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_admin_client()

        # Delete existing chunks for this file
        client.table('pdf_chunks') \
            .delete() \
            .eq('filename', filename) \
            .execute()

        if not chunks:
            logger.info(f"No chunks to save for {filename}")
            return True

        # Insert new chunks in batches
        rows = [
            {
                'filename': filename,
                'chunk_index': i,
                'chunk_text': chunk
            }
            for i, chunk in enumerate(chunks)
        ]

        # Batch insert (Supabase has row limits)
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            client.table('pdf_chunks').insert(batch).execute()

        # Update metadata
        client.table('document_metadata').upsert({
            'filename': filename,
            'chunk_count': len(chunks),
            'processed_at': datetime.now().isoformat()
        }, on_conflict='filename').execute()

        logger.info(f"Saved {len(chunks)} chunks for {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save document chunks: {e}")
        return False


def load_all_chunks() -> List[Dict[str, Any]]:
    """
    Load all document chunks from the database with metadata.

    Returns:
        List of dicts: [{'content': str, 'filename': str, 'chunk_index': int, 'document_id': str}]
    """
    try:
        client = get_supabase_client()

        # First, build document_id -> filename map
        doc_id_to_filename = {}
        try:
            docs_result = client.table('pdf_documents').select('id, filename').execute()
            if docs_result.data:
                for doc in docs_result.data:
                    doc_id_to_filename[doc['id']] = doc.get('filename', '')
        except Exception as e:
            logger.warning(f"Could not load document filenames: {e}")

        # Get total count first
        count_result = client.table('pdf_chunks') \
            .select('id', count='exact') \
            .execute()

        total_count = count_result.count or 0

        if total_count == 0:
            logger.info("No chunks found in database")
            return []

        # Fetch all chunks (paginated if necessary)
        all_chunks = []
        page_size = 1000
        offset = 0

        while offset < total_count:
            result = client.table('pdf_chunks') \
                .select('document_id, chunk_index, content') \
                .order('document_id') \
                .order('chunk_index') \
                .range(offset, offset + page_size - 1) \
                .execute()

            if result.data:
                for row in result.data:
                    # Attach filename via document_id lookup
                    row['filename'] = doc_id_to_filename.get(row.get('document_id'), '')
                    all_chunks.append(row)

            offset += page_size

        logger.info(f"Loaded {len(all_chunks)} chunks from {len(doc_id_to_filename)} documents")
        return all_chunks
    except Exception as e:
        logger.error(f"Failed to load chunks: {e}")
        return []


def get_document_metadata() -> List[Dict[str, Any]]:
    """
    Get metadata for all processed documents.

    Returns:
        List of document metadata dicts
    """
    try:
        client = get_supabase_client()
        result = client.table('pdf_documents') \
            .select('id, filename, chunk_count, processed_at, status') \
            .order('filename') \
            .execute()

        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get document metadata: {e}")
        return []


def remove_document(filename: str) -> bool:
    """
    Remove a document and its chunks from the database.

    Args:
        filename: The document filename to remove

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_admin_client()

        # Get document ID first
        doc_result = client.table('pdf_documents') \
            .select('id') \
            .eq('filename', filename) \
            .single() \
            .execute()

        if not doc_result.data:
            logger.warning(f"Document {filename} not found")
            return False

        doc_id = doc_result.data['id']

        # Delete chunks by document_id
        client.table('pdf_chunks') \
            .delete() \
            .eq('document_id', doc_id) \
            .execute()

        # Delete document metadata
        client.table('pdf_documents') \
            .delete() \
            .eq('id', doc_id) \
            .execute()

        logger.info(f"Removed document {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove document: {e}")
        return False


# -------------------------
# Conversation History Operations
# Uses: conversations (sessions) and messages (individual Q&A)
# -------------------------

def get_or_create_conversation(session_id: str, user_id: str) -> Optional[str]:
    """
    Get or create a conversation for a session.

    Returns:
        The conversation UUID, or None on error
    """
    try:
        client = get_supabase_client()

        # Try to find existing conversation
        result = client.table('conversations') \
            .select('id') \
            .eq('session_id', session_id) \
            .eq('user_id', user_id) \
            .limit(1) \
            .execute()

        if result.data:
            return result.data[0]['id']

        # Create new conversation
        new_result = client.table('conversations').insert({
            'session_id': session_id,
            'user_id': user_id,
            'title': 'Chat Session',
            'is_active': True
        }).execute()

        if new_result.data:
            return new_result.data[0]['id']

        return None
    except Exception as e:
        logger.error(f"Failed to get/create conversation: {e}")
        return None


def add_conversation(session_id: str, user_id: str, question: str, answer: str,
                     metadata: dict = None) -> bool:
    """
    Add a conversation entry (question + answer as two messages).

    Args:
        session_id: The chat session ID
        user_id: The user's UUID
        question: The user's question
        answer: The AI's response
        metadata: Optional additional metadata

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_supabase_client()

        # Get or create conversation
        conversation_id = get_or_create_conversation(session_id, user_id)
        if not conversation_id:
            return False

        # Get next sequence number
        count_result = client.table('messages') \
            .select('id', count='exact') \
            .eq('conversation_id', conversation_id) \
            .execute()
        next_seq = (count_result.count or 0) + 1

        # Insert user message
        client.table('messages').insert({
            'conversation_id': conversation_id,
            'user_id': user_id,
            'role': 'user',
            'content': question,
            'sequence_number': next_seq
        }).execute()

        # Insert assistant message
        client.table('messages').insert({
            'conversation_id': conversation_id,
            'user_id': user_id,
            'role': 'assistant',
            'content': answer,
            'sequence_number': next_seq + 1
        }).execute()

        logger.debug(f"Added conversation for session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to add conversation: {e}")
        return False


def get_conversation_history(session_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    Get recent conversation history for a session.

    Args:
        session_id: The chat session ID
        limit: Maximum number of message pairs to return

    Returns:
        List of conversation entries with question/answer (oldest first)
    """
    try:
        client = get_supabase_client()

        # Find conversation by session_id
        conv_result = client.table('conversations') \
            .select('id') \
            .eq('session_id', session_id) \
            .limit(1) \
            .execute()

        if not conv_result.data:
            return []

        conversation_id = conv_result.data[0]['id']

        # Get messages (most recent first, then reverse)
        result = client.table('messages') \
            .select('role, content, created_at') \
            .eq('conversation_id', conversation_id) \
            .order('sequence_number', desc=True) \
            .limit(limit * 2) \
            .execute()

        if not result.data:
            return []

        # Reverse to chronological order and pair up messages
        messages = list(reversed(result.data))
        conversations = []

        i = 0
        while i < len(messages) - 1:
            if messages[i]['role'] == 'user' and messages[i + 1]['role'] == 'assistant':
                conversations.append({
                    'question': messages[i]['content'],
                    'answer': messages[i + 1]['content'],
                    'created_at': messages[i]['created_at']
                })
                i += 2
            else:
                i += 1

        return conversations
    except Exception as e:
        logger.error(f"Failed to get conversation history: {e}")
        return []


def clear_conversation_history(session_id: str, user_id: str) -> bool:
    """
    Clear conversation history for a session.

    Args:
        session_id: The chat session ID
        user_id: The user's UUID (for RLS)

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_supabase_client()

        # Find conversation
        conv_result = client.table('conversations') \
            .select('id') \
            .eq('session_id', session_id) \
            .eq('user_id', user_id) \
            .limit(1) \
            .execute()

        if not conv_result.data:
            return True  # Nothing to clear

        conversation_id = conv_result.data[0]['id']

        # Delete messages
        client.table('messages') \
            .delete() \
            .eq('conversation_id', conversation_id) \
            .execute()

        # Delete conversation
        client.table('conversations') \
            .delete() \
            .eq('id', conversation_id) \
            .execute()

        logger.info(f"Cleared conversation history for session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear conversation history: {e}")
        return False


# -------------------------
# User Acknowledgement Operations
# -------------------------

def check_acknowledgement(user_id: str) -> Dict[str, Any]:
    """
    Check the current acknowledgement + consent state for a user.

    Returns a dict (not just a bool) so the API layer can decide whether the
    user needs to re-consent under the new MHMDA flow:
      {
        'acknowledged': bool,            # has any acknowledgement row
        'consent_version': str | None,   # last accepted version
        'consent_metadata': dict,        # full audit JSONB (may be empty for pre-v2)
        'state_restricted': bool,        # user previously declared IL/NV
      }
    """
    try:
        client = get_admin_client()
        # Be defensive: the new columns may not yet exist on every environment.
        # Try the full select first; fall back to the legacy id-only check.
        try:
            result = client.table('user_acknowledgements') \
                .select('id, consent_version, consent_metadata') \
                .eq('user_id', user_id) \
                .limit(1) \
                .execute()
        except Exception:
            result = client.table('user_acknowledgements') \
                .select('id') \
                .eq('user_id', user_id) \
                .limit(1) \
                .execute()

        if not result.data:
            return {
                'acknowledged': False,
                'consent_version': None,
                'consent_metadata': {},
                'state_restricted': False,
            }

        row = result.data[0]
        metadata = row.get('consent_metadata') or {}
        state = (metadata.get('state') or '').upper() if isinstance(metadata, dict) else ''
        from compliance import BLOCKED_STATES
        return {
            'acknowledged': True,
            'consent_version': row.get('consent_version'),
            'consent_metadata': metadata if isinstance(metadata, dict) else {},
            'state_restricted': state in BLOCKED_STATES,
        }
    except Exception as e:
        logger.error(f"Failed to check acknowledgement for user {user_id}: {e}")
        return {
            'acknowledged': False,
            'consent_version': None,
            'consent_metadata': {},
            'state_restricted': False,
        }


def save_acknowledgement(user_id: str, consent_metadata: Dict[str, Any] = None,
                          consent_version: str = None) -> bool:
    """
    Save a user's acknowledgement + MHMDA consent record.

    Args:
        user_id: The user's UUID
        consent_metadata: Full consent record (see lib.compliance.build_consent_metadata)
        consent_version: The version tag of the consent terms accepted

    Returns:
        True if successful, False otherwise

    Backwards-compatible: callers that don't pass consent_metadata still work
    (legacy "v1" acknowledgement just records the user clicked OK).
    """
    try:
        client = get_admin_client()
        row = {
            'user_id': user_id,
            'acknowledged_at': datetime.now().isoformat(),
            'acknowledgement_version': '1.0',
        }
        if consent_version:
            row['consent_version'] = consent_version
        if consent_metadata is not None:
            row['consent_metadata'] = consent_metadata

        # Try full upsert (new columns); fall back to legacy if columns don't exist
        try:
            client.table('user_acknowledgements').upsert(
                row, on_conflict='user_id'
            ).execute()
        except Exception as e:
            # Likely the new columns aren't migrated yet — fall back to legacy fields
            logger.warning(f"Full acknowledgement upsert failed ({e}); retrying with legacy fields")
            client.table('user_acknowledgements').upsert({
                'user_id': user_id,
                'acknowledged_at': datetime.now().isoformat(),
                'acknowledgement_version': '1.0',
            }, on_conflict='user_id').execute()

        logger.info(f"Saved acknowledgement for user {user_id} (version={consent_version})")
        return True
    except Exception as e:
        logger.error(f"Failed to save acknowledgement for user {user_id}: {e}")
        return False


# -------------------------
# Chat Message Persistence
# -------------------------

def save_chat_message(user_id: str, role: str, content: str, metadata: dict = None) -> bool:
    """
    Save a chat message for a user.

    Args:
        user_id: The user's UUID
        role: 'user' or 'assistant'
        content: The message content
        metadata: Optional metadata (e.g., clinical_trials data)

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_admin_client()
        data = {
            'user_id': user_id,
            'role': role,
            'content': content
        }
        # Add metadata if provided (requires metadata JSONB column in chat_messages table)
        if metadata:
            data['metadata'] = metadata

        client.table('chat_messages').insert(data).execute()

        logger.debug(f"Saved {role} message for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save chat message for user {user_id}: {e}")
        return False


def load_chat_history(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Load chat history for a user.

    Args:
        user_id: The user's UUID
        limit: Maximum number of messages to return

    Returns:
        List of message dicts with role, content, created_at, metadata (oldest first)
    """
    try:
        client = get_admin_client()
        result = client.table('chat_messages') \
            .select('role, content, created_at, metadata') \
            .eq('user_id', user_id) \
            .order('created_at', desc=True) \
            .limit(limit) \
            .execute()

        if not result.data:
            return []

        # Reverse to chronological order (oldest first)
        messages = list(reversed(result.data))
        logger.info(f"Loaded {len(messages)} chat messages for user {user_id}")
        return messages
    except Exception as e:
        logger.error(f"Failed to load chat history for user {user_id}: {e}")
        return []


def clear_chat_history(user_id: str) -> bool:
    """
    Clear all chat history for a user.

    Args:
        user_id: The user's UUID

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_admin_client()
        client.table('chat_messages') \
            .delete() \
            .eq('user_id', user_id) \
            .execute()

        logger.info(f"Cleared chat history for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear chat history for user {user_id}: {e}")
        return False


# =============================================================================
# SCREENING SCORES (Items 3, 4, 5 - PHQ-9/GAD-7/PSS-10/ISI)
# =============================================================================

def save_screening_score(user_id: str, instrument: str, scores: dict,
                          total_score: int, severity_label: str) -> bool:
    """Save a completed screening instrument score."""
    try:
        client = get_admin_client()
        client.table('screening_scores').insert({
            'user_id': user_id,
            'instrument': instrument,
            'scores': scores,
            'total_score': total_score,
            'severity_label': severity_label,
            'completed_at': datetime.now().isoformat()
        }).execute()
        logger.info(f"Saved {instrument} score for user {user_id}: {total_score} ({severity_label})")
        return True
    except Exception as e:
        logger.error(f"Failed to save screening score: {e}")
        return False


def load_latest_screening_score(user_id: str, instrument: str) -> dict:
    """Load the most recent score for a given instrument."""
    try:
        client = get_admin_client()
        result = client.table('screening_scores') \
            .select('*') \
            .eq('user_id', user_id) \
            .eq('instrument', instrument) \
            .order('completed_at', desc=True) \
            .limit(1) \
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to load screening score: {e}")
        return None


def load_screening_history(user_id: str, instrument: str, limit: int = 20) -> list:
    """Load screening history for trend tracking."""
    try:
        client = get_admin_client()
        result = client.table('screening_scores') \
            .select('total_score, severity_label, completed_at') \
            .eq('user_id', user_id) \
            .eq('instrument', instrument) \
            .order('completed_at', desc=True) \
            .limit(limit) \
            .execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to load screening history: {e}")
        return []


def load_all_screening_history(user_id: str) -> dict:
    """Load screening history for all instruments, grouped by instrument."""
    instruments = ['PHQ9', 'GAD7', 'PSS10', 'ISI', 'SYMPTOM', 'PREMM5']
    history = {}
    for inst in instruments:
        data = load_screening_history(user_id, inst, limit=20)
        if data:
            # Return in chronological order (oldest first) for charting
            history[inst] = list(reversed(data))
    return history


def delete_all_user_data(user_id: str) -> dict:
    """
    Delete ALL data for a user across all tables.

    GDPR Article 17 + WA MHMDA + CCPA compliance. Returns a structured dict
    with per-table deletion results.

    Scope of this function (under our direct control):
      - patient_profiles      — full row
      - chat_messages         — all rows for user
      - screening_scores      — all rows for user
      - user_acknowledgements — full row including consent_metadata
      - chat_feedback         — all rows for user
      - conversations         — all rows for user
      - messages              — all rows for user
      - rate_limits           — all rows for user_id (as identifier)

    Sub-processor data NOT under our direct control (documented in
    docs/compliance/subprocessor_chain.md — retention per their ToS):
      - Together AI / Groq inference logs — typically retained ~30 days by
        the provider; we send only de-identified queries.
      - Supabase backups — auto-purged on the rolling window per Supabase
        retention policy (PITR 7 days by default).
      - Vercel function logs — short retention per Vercel ToS; contains
        request metadata, not application data.

    Returns dict with deletion results per table + a sub_processors_notice
    field that the caller logs for the audit trail.
    """
    import hashlib
    user_hash = hashlib.sha256((user_id or "").encode("utf-8")).hexdigest()[:16]

    results = {}
    try:
        client = get_admin_client()

        tables = [
            'patient_profiles',
            'chat_messages',
            'screening_scores',
            'user_acknowledgements',
            'chat_feedback',
            'conversations',
            'messages',
            'rate_limits',
        ]

        for table in tables:
            try:
                client.table(table).delete().eq('user_id', user_id).execute()
                results[table] = 'deleted'
            except Exception as e:
                results[table] = f'error: {str(e)}'

        # rate_limits is keyed by 'identifier' (which is user_id for chat / appeal endpoints).
        try:
            client.table('rate_limits').delete().eq('identifier', user_id).execute()
        except Exception:
            pass

        # Structured deletion-audit log line. user_hash (not user_id) so we have an
        # audit trail without retaining the user identifier in logs.
        # This satisfies the documented audit trail in docs/compliance/incident_response_plan.md.
        logger.info(
            "DELETION_AUDIT user_hash=%s tables=%s timestamp=%s",
            user_hash,
            ",".join(t for t, r in results.items() if r == 'deleted'),
            datetime.now().isoformat(),
        )

        results['sub_processors_notice'] = (
            "Sub-processor data (Together AI, Groq, Supabase backups, Vercel logs) "
            "is purged per their retention policies; see docs/compliance/subprocessor_chain.md."
        )
        return results

    except Exception as e:
        logger.error(f"Failed to delete user data: {e}")
        return {'error': str(e)}
