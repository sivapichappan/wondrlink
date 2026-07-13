/**
 * Conversations API wrappers (multi-conversation drawer).
 *
 * Backs New chat / Recents / Search. Unlike the legacy single-thread flow,
 * the server is the sole writer — /api/chat persists both turns to the named
 * conversation, so there is no client-side save_message here.
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  ChatHistoryResponse,
  Conversation,
  ConversationsListResponse,
  CreateConversationResponse,
} from '@shared/types';

import { apiFetch } from './client';

export function fetchConversations(limit = 100) {
  return apiFetch<ConversationsListResponse>(`${ENDPOINTS.conversations}?limit=${limit}`, {
    method: 'GET',
  }).then((r) => r.conversations ?? []);
}

export function createConversation(title?: string) {
  return apiFetch<CreateConversationResponse>(ENDPOINTS.conversations, {
    method: 'POST',
    body: title ? { title } : {},
  });
}

export function searchConversations(query: string) {
  return apiFetch<ConversationsListResponse>(
    `${ENDPOINTS.conversationsSearch}?q=${encodeURIComponent(query)}`,
    { method: 'GET' },
  ).then((r) => r.conversations ?? []);
}

export function fetchConversationMessages(id: string, limit = 200) {
  return apiFetch<ChatHistoryResponse>(
    `${ENDPOINTS.conversationMessages(id)}?limit=${limit}`,
    { method: 'GET' },
  );
}

export function renameConversation(id: string, title: string) {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.conversation(id), {
    method: 'PATCH',
    body: { title },
  });
}

export function deleteConversation(id: string) {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.conversation(id), {
    method: 'DELETE',
  });
}

export type { Conversation };
