# branding.py
"""
Product branding — THE single source of the product name (Python side).

Supervisor rule (2026-07-25): the app name lives in one config constant; a
future rename is a one-line change here, not a refactor. Backend strings
and prompt templates interpolate APP_NAME (prompt files carry an
{app_name} slot rendered at load/assembly time, so the text the model
sees is unchanged until this constant changes).

NEVER derived from this file (identifiers are permanent): the
wondrchat.vercel.app apiBase, env var names, database table names, and
storage keys.

TypeScript mirror: shared/branding.ts. Web SPA mirror: the APP_NAME const
in public/index.html. Keep all three in sync.
"""

# What the product calls itself in UI and conversation.
APP_NAME = "Sage"

# The App Store listing name (unique on the store; 'Sage' was taken).
APP_STORE_NAME = "MySage"

# The legal entity — NOT the product; never replace with APP_NAME.
LEGAL_ENTITY = "WondrLink Foundation"
