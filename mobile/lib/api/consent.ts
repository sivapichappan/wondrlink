/**
 * Consent API wrappers.
 *
 * - checkAcknowledgement() GET /api/check_acknowledgement
 *   Returns whether the current logged-in user has accepted the current
 *   CURRENT_CONSENT_VERSION (lib/compliance.py). Mobile routes through the
 *   onboarding flow when needs_consent=true or state_restricted=true.
 *
 * - saveAcknowledgement() POST /api/save_acknowledgement
 *   Sends age_confirmed + state + the three MHMDA consents. Server returns
 *   HTTP 422 for blocked states (IL/NV) and 400 for missing consents.
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  CheckAcknowledgementResponse,
  SaveAcknowledgementRequest,
  SaveAcknowledgementResponse,
} from '@shared/types';

import { apiFetch } from './client';

export function checkAcknowledgement() {
  return apiFetch<CheckAcknowledgementResponse>(ENDPOINTS.checkAcknowledgement, {
    method: 'GET',
  });
}

export function saveAcknowledgement(payload: SaveAcknowledgementRequest) {
  return apiFetch<SaveAcknowledgementResponse>(ENDPOINTS.saveAcknowledgement, {
    method: 'POST',
    body: payload,
  });
}
