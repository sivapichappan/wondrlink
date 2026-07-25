/**
 * Product branding — THE single source of the product name.
 *
 * Supervisor rule (2026-07-25): the app name lives in one config constant;
 * a future rename is a one-line change here, not a refactor. Every
 * user-visible string interpolates APP_NAME. The App Store LISTING name
 * (unique on the store) may differ from the product name the app calls
 * itself in conversation.
 *
 * NEVER derived from this file (identifiers are permanent): bundle ID
 * org.wondrlink.wondrchat, EAS slug/projectId, apiBase wondrchat.vercel.app,
 * AsyncStorage keys (e.g. 'sage:still_finding_out'), env var names, and
 * database table names.
 *
 * Python mirror: lib/branding.py. Web SPA mirror: the APP_NAME const at the
 * top of public/index.html's script. Keep all three in sync.
 */

/** What the product calls itself in UI and conversation. */
export const APP_NAME = 'Sage';

/** The App Store listing name (unique on the store; 'Sage' was taken). */
export const APP_STORE_NAME = 'MySage';

/** Product domain (owned; DNS cutover still an open question). */
export const APP_DOMAIN = 'mysage.chat';

/** The legal entity — NOT the product; never replace with APP_NAME. */
export const LEGAL_ENTITY = 'WondrLink Foundation';
