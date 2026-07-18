/**
 * Account / compliance API wrappers.
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  AccountBasicsRequest,
  FeedbackRequest,
  LimitSpiResponse,
  PrivacyAppealRequest,
  PrivacyAppealResponse,
} from '@shared/types';

import { apiFetch } from './client';

/** Sage onboarding basics (who-for + the four facts). */
export function saveAccountBasics(basics: AccountBasicsRequest) {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.accountBasics, {
    method: 'POST',
    body: basics,
  });
}

export function submitPrivacyAppeal(body: PrivacyAppealRequest) {
  return apiFetch<PrivacyAppealResponse>(ENDPOINTS.privacyAppeal, {
    method: 'POST',
    body,
  });
}

export function submitFeedback(body: FeedbackRequest) {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.feedback, {
    method: 'POST',
    body,
  });
}

export function deleteAccount() {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.deleteAccount, {
    method: 'DELETE',
  });
}

// CCPA / CPRA "Limit Use of Sensitive Personal Information" (Task 5).
// GET returns the current preference + timestamp; POST records it.
// Operationally a no-op because we don't use SPI for advertising or sale.
export function getLimitSpi() {
  return apiFetch<LimitSpiResponse>(ENDPOINTS.limitSensitivePi, { method: 'GET' });
}

export function confirmLimitSpi() {
  return apiFetch<{ status: 'ok' } & LimitSpiResponse>(ENDPOINTS.limitSensitivePi, {
    method: 'POST',
  });
}
