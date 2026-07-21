/**
 * Chat API wrappers.
 *
 * The backend does not auto-persist messages from /api/chat — the client is
 * expected to POST /api/save_message for both the user message and the
 * resulting bot message. That gives us the ability to optimistically render
 * before the save round-trips.
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  ChatHistoryResponse,
  ChatRequest,
  ChatResponse,
  LogSymptomRequest,
  SaveMessageRequest,
} from '@shared/types';

import { apiFetch } from './client';

/** T2 escalation card action: put the symptom on the record with a timestamp. */
export function logSymptom(body: LogSymptomRequest) {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.safetyLogSymptom, {
    method: 'POST',
    body,
  });
}

export function sendChatMessage(body: ChatRequest) {
  return apiFetch<ChatResponse>(ENDPOINTS.chat, {
    method: 'POST',
    body,
  });
}

export function fetchChatHistory(limit = 50) {
  return apiFetch<ChatHistoryResponse>(`${ENDPOINTS.chatHistory}?limit=${limit}`, {
    method: 'GET',
  });
}

export function saveMessage(body: SaveMessageRequest) {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.saveMessage, {
    method: 'POST',
    body,
  });
}

export function clearChatHistory() {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.clearChat, {
    method: 'DELETE',
  });
}

/** Resolve an "is that right?" belief confirmation chip. */
export function confirmBelief(confirmationId: string, accept: boolean) {
  return apiFetch<{
    status: 'confirmed' | 'rejected';
    path?: string;
    corrected_question?: string;
  }>(ENDPOINTS.confirmBelief, {
    method: 'POST',
    body: { confirmation_id: confirmationId, accept },
  });
}
