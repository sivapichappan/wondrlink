/**
 * Consent versioning + state-policy constants.
 *
 * Mirrors lib/compliance.py. When the Python file changes, update this file
 * in the same commit. The server is the authority — these constants exist
 * so the mobile client knows what version it currently believes is in force,
 * which states it should block at signup, and which checkboxes the consent
 * screen must show.
 */

/**
 * Bump in lib/compliance.py FIRST. Mobile reads the live version from
 * /api/check_acknowledgement.current_version; this constant is for typing,
 * documentation, and the consent screen's display string.
 */
export const CURRENT_CONSENT_VERSION = 'v2-mhmda-2026-05';

/**
 * States blocked at signup. The server returns HTTP 422 with a soft-deactivation
 * message; the client should route to the StateRestricted screen.
 *
 *   IL: WOPR Act (effective Aug 4, 2025)
 *   NV: AB 406 (effective Jul 1, 2025)
 */
export const BLOCKED_STATES = ['IL', 'NV'] as const;
export type BlockedState = (typeof BLOCKED_STATES)[number];

/**
 * States with specific privacy regimes we comply with via the full opt-in flow.
 *   WA: My Health My Data Act (MHMDA)
 */
export const MHMDA_STATES = ['WA'] as const;
export type MhmdaState = (typeof MHMDA_STATES)[number];

/**
 * US state + territory codes the dropdown accepts. 'non_US' is the
 * outside-US sentinel — it still requires all three consents.
 */
export const US_STATES = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
  'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
  'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
  'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
  'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
  'DC', 'PR', 'VI', 'GU', 'AS', 'MP',
] as const;
export type UsState = (typeof US_STATES)[number];
export type StateChoice = UsState | 'non_US';

/**
 * Three MHMDA-required consents. All three must be independent affirmative
 * acts — no pre-checking, no bundling.
 */
export const REQUIRED_CONSENT_FIELDS = [
  'consent_collection',
  'consent_sharing',
  'consent_terms',
] as const;
export type ConsentField = (typeof REQUIRED_CONSENT_FIELDS)[number];

export function isValidState(state: string): state is StateChoice {
  if (!state) return false;
  if (state === 'non_US') return true;
  return (US_STATES as readonly string[]).includes(state.toUpperCase());
}

export function isBlockedState(state: string): boolean {
  if (!state) return false;
  return (BLOCKED_STATES as readonly string[]).includes(state.toUpperCase());
}
