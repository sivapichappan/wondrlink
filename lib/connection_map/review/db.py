"""The restricted database client for review handlers (SPEC §5.8).

Every query a reviewer causes runs as the Postgres role `sage_review`, which
has zero privileges on patient tables. A query for patient data fails at the
database with "permission denied for table", not because our code declined to
issue it. That is the whole point: the guarantee is demonstrable to an auditor
rather than a promise about our own routing.

HOW THE ROLE IS SELECTED. Supabase has no connection pool we can address, so
this uses the mechanism PostgREST supports natively: a JWT carrying
`{"role": "sage_review"}`, signed with the project's JWT secret. PostgREST
switches into that role for the request. The role is NOLOGIN and reachable
only through `authenticator`, so the token is the only way in.

FAIL CLOSED, ALWAYS. If the secret is missing, the token cannot be minted, or
anything else goes wrong, this raises. It must NEVER fall back to the
service-role client — that client bypasses RLS and can read every patient
table, so a "helpful" fallback would silently delete the entire boundary while
appearing to work. That is the single most dangerous edit anyone could make to
this file.
"""

import os
import threading
import time
from typing import Any, Optional

import jwt
from supabase import create_client

# The role name must match the migration. Changing one without the other
# yields a token PostgREST rejects.
REVIEW_ROLE = "sage_review"

# Short-lived by design: the token grants review access for as long as it is
# valid, so it is minted per use-window rather than issued once and stored.
TOKEN_TTL_SECONDS = 600
_RENEW_MARGIN_SECONDS = 60

_lock = threading.Lock()
_cached_token: Optional[str] = None
_cached_expiry: float = 0.0
_cached_client: Any = None


class ReviewBoundaryError(RuntimeError):
    """Raised when the restricted client cannot be built.

    Callers must let this surface. Catching it and substituting any other
    client defeats §5.8.
    """


def _jwt_secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise ReviewBoundaryError(
            "SUPABASE_JWT_SECRET is not set; the review client cannot be built. "
            "Refusing to continue: there is no safe fallback, because every "
            "other client in this app bypasses RLS.")
    return secret


def mint_review_token(now: Optional[float] = None) -> str:
    """Mint a short-lived JWT selecting the sage_review role."""
    issued = int(now if now is not None else time.time())
    claims = {
        "role": REVIEW_ROLE,
        "iat": issued,
        "exp": issued + TOKEN_TTL_SECONDS,
    }
    token = jwt.encode(claims, _jwt_secret(), algorithm="HS256")
    # PyJWT >= 2 returns str; older returns bytes.
    return token.decode("utf-8") if isinstance(token, bytes) else token


def _supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise ReviewBoundaryError("SUPABASE_URL is not set; cannot build the review client")
    return url


def _anon_key() -> str:
    # The anon key only gets the request to PostgREST; the JWT below decides
    # what it may touch. The service-role key is deliberately never read here.
    key = os.environ.get("SUPABASE_KEY")
    if not key:
        raise ReviewBoundaryError("SUPABASE_KEY is not set; cannot build the review client")
    return key


def get_review_client(now: Optional[float] = None) -> Any:
    """Supabase client whose PostgREST calls execute as sage_review.

    Cached and re-authenticated when the token nears expiry. Raises
    ReviewBoundaryError rather than degrading.
    """
    global _cached_token, _cached_expiry, _cached_client

    current = now if now is not None else time.time()
    with _lock:
        if _cached_client is not None and current < _cached_expiry - _RENEW_MARGIN_SECONDS:
            return _cached_client

        token = mint_review_token(current)
        client = _cached_client or create_client(_supabase_url(), _anon_key())
        # Attaches Authorization: Bearer <token> to PostgREST calls, which is
        # what makes the role switch happen.
        client.postgrest.auth(token)

        _cached_token = token
        _cached_expiry = current + TOKEN_TTL_SECONDS
        _cached_client = client
        return client


def reset_review_client() -> None:
    """Drop the cached client and token. For tests and key rotation."""
    global _cached_token, _cached_expiry, _cached_client
    with _lock:
        _cached_token = None
        _cached_expiry = 0.0
        _cached_client = None


def describe_boundary() -> dict:
    """Non-secret description of the boundary, for /api/health style checks.

    Deliberately reports only whether configuration is present, never any part
    of a key or token.
    """
    return {
        "role": REVIEW_ROLE,
        "configured": bool(os.environ.get("SUPABASE_JWT_SECRET"))
        and bool(os.environ.get("SUPABASE_URL"))
        and bool(os.environ.get("SUPABASE_KEY")),
        "token_ttl_seconds": TOKEN_TTL_SECONDS,
    }
