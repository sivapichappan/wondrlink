# supabase_auth.py
import logging
from typing import Tuple, Optional, Dict, Any
from supabase_client import get_supabase_client, verify_token

logger = logging.getLogger("supabase_auth")


def register_user(email: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Register a new user with Supabase Auth.

    Args:
        email: User's email address
        password: User's password

    Returns:
        Tuple of (user_data, error_message)
        - On success: ({"user_id": ..., "email": ..., "access_token": ...}, None)
        - On failure: (None, error_message)
    """
    if not email or not password:
        return None, "Email and password are required"

    if len(password) < 8:
        return None, "Password must be at least 8 characters"

    import re
    if not re.search(r'[A-Z]', password):
        return None, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return None, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return None, "Password must contain at least one number"

    try:
        client = get_supabase_client()
        response = client.auth.sign_up({
            "email": email,
            "password": password
        })

        if response.user:
            # Supabase v2 anti-enumeration: when an email is already registered,
            # sign_up() returns a user object with an EMPTY identities array
            # (instead of raising "already registered"). We detect this here and
            # return a clear error so the mobile / web client can route the user
            # to "Log in" instead of showing a misleading "check your email" UI.
            identities = getattr(response.user, "identities", None)
            if identities is not None and len(identities) == 0:
                logger.info("Repeated signup attempt for an already-registered email")
                return None, "Email already registered. Please log in instead."

            logger.info(f"User registered: user_id={response.user.id}")
            return {
                "user_id": response.user.id,
                "email": response.user.email,
                "access_token": response.session.access_token if response.session else None,
                "refresh_token": response.session.refresh_token if response.session else None
            }, None
        else:
            return None, "Registration failed"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Registration error: {error_msg}")

        # Parse common Supabase auth errors
        if "already registered" in error_msg.lower() or "already exists" in error_msg.lower():
            return None, "Email already registered"
        if "invalid email" in error_msg.lower():
            return None, "Invalid email format"

        return None, f"Registration failed: {error_msg}"


def login_user(email: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Authenticate a user with email and password.

    Args:
        email: User's email address
        password: User's password

    Returns:
        Tuple of (user_data, error_message)
        - On success: ({"user_id": ..., "email": ..., "access_token": ...}, None)
        - On failure: (None, error_message)
    """
    if not email or not password:
        return None, "Email and password are required"

    try:
        client = get_supabase_client()
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user and response.session:
            logger.info(f"User logged in: user_id={response.user.id}")
            return {
                "user_id": response.user.id,
                "email": response.user.email,
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token
            }, None
        else:
            return None, "Invalid credentials"

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Login failed: {error_msg}")

        if "invalid" in error_msg.lower() or "credentials" in error_msg.lower():
            return None, "Invalid email or password"

        return None, "Login failed"


def logout_user(access_token: str) -> bool:
    """
    Sign out a user.

    Args:
        access_token: The user's current access token

    Returns:
        True if logout successful, False otherwise
    """
    try:
        client = get_supabase_client()
        client.auth.sign_out()
        logger.info("User logged out")
        return True
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return False


def get_current_user(access_token: str) -> Optional[Dict[str, Any]]:
    """
    Get the current user's information from their access token.

    Args:
        access_token: JWT access token

    Returns:
        User dict if valid, None if invalid
    """
    return verify_token(access_token)


def refresh_session(refresh_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Refresh an expired session using a refresh token.

    Args:
        refresh_token: The refresh token

    Returns:
        Tuple of (new_session_data, error_message)
    """
    try:
        client = get_supabase_client()
        response = client.auth.refresh_session(refresh_token)

        if response.session:
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "user_id": response.user.id if response.user else None
            }, None
        else:
            return None, "Failed to refresh session"

    except Exception as e:
        logger.error(f"Session refresh error: {e}")
        return None, str(e)
