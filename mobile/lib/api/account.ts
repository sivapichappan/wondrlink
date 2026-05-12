/**
 * Account / compliance API wrappers.
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  FeedbackRequest,
  PrivacyAppealRequest,
  PrivacyAppealResponse,
} from '@shared/types';

import { apiFetch } from './client';

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
