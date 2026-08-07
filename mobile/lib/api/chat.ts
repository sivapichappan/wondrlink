/**
 * Chat API wrappers.
 *
 * The SERVER is the sole writer: /api/chat persists both turns before it
 * responds, so the answer exists whether or not the response reaches us. That
 * is what makes recovery possible at all — see fetchTurnStatus below.
 * (/api/save_message is legacy and is no longer on the send path.)
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  ChatHistoryResponse,
  ChatRequest,
  ChatResponse,
  ChatTurnStatus,
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

/**
 * Has this question been answered yet?
 *
 * Polled after the app comes back from the background, where the in-flight
 * request was almost certainly killed by the OS. One indexed row rather than
 * re-reading the whole thread every few seconds, and it carries the
 * conversation id — which a brand-new thread never learned, because the
 * response holding it died with the socket.
 */
export function fetchTurnStatus(clientTurnId: string) {
  return apiFetch<ChatTurnStatus>(ENDPOINTS.chatTurnStatus(clientTurnId), {
    method: 'GET',
  });
}

/**
 * Ask to be notified when the answer lands, because we are being backgrounded.
 *
 * FIRE AND FORGET, and it never throws. It runs from an AppState handler with
 * only a few seconds of runtime before iOS suspends everything, so it either
 * makes it out or it does not — and if it does not, silent recovery still
 * brings the answer back the next time the app is opened.
 */
export function requestNotifyWhenReady(clientTurnId: string): void {
  apiFetch<{ status: string; notified: boolean }>(ENDPOINTS.chatNotifyWhenReady, {
    method: 'POST',
    body: { client_turn_id: clientTurnId },
  }).catch(() => {});
}

/**
 * Ask the server to pull the guideline corpus into memory before the first
 * real question.
 *
 * A cold container spends about 9 seconds loading a corpus that never changes,
 * and the person pays that AFTER hitting send. Firing this while they are still
 * reading and typing moves the wait somewhere they do not notice it.
 *
 * FIRE AND FORGET, and it never throws: the whole point is that it happens
 * where nobody is watching, so a failure must not surface to someone who was
 * only trying to open a chat. Worst case they get today's speed.
 */
export function warmUp(): void {
  apiFetch<{ status: 'ok'; warmed: boolean }>(ENDPOINTS.warm, { method: 'POST' })
    .catch(() => {});
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
