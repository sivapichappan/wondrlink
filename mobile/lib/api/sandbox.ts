/**
 * The chat a reviewer tests on (SPEC §5.5).
 *
 * A reviewer may not hold a patient profile — the database enforces it in both
 * directions — so there is no patient chat route a reviewer could use. These
 * endpoints run the same answer pipeline over a SYNTHETIC patient held in its
 * own tables, which is why the property "a reviewer cannot open a real
 * patient's chat" needs no filter anywhere: there is no patient id in the path.
 *
 * Response shapes deliberately mirror lib/api/chat.ts and lib/api/conversations
 * so the chat screen does not need a second set of components.
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  ChatHistoryMessage,
  ChatRequest,
  ChatResponse,
  Conversation,
} from '@shared/types';

import { apiFetch } from './client';

export function sendSandboxMessage(body: ChatRequest) {
  return apiFetch<ChatResponse>(ENDPOINTS.sandboxChat, {
    method: 'POST',
    body,
  });
}

interface SandboxConversationRow {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

/** Returns the same `Conversation` shape the patient list does, so the drawer's
 *  Recents renders both without a branch. The title is nullable in the table
 *  and never is on screen. */
export function fetchSandboxConversations(): Promise<Conversation[]> {
  return apiFetch<{ status: 'ok'; conversations: SandboxConversationRow[] }>(
    ENDPOINTS.sandboxConversations,
    { method: 'GET' },
  ).then((r) =>
    (r.conversations ?? []).map((c) => ({
      id: c.id,
      title: c.title ?? 'Test conversation',
      created_at: c.created_at,
      updated_at: c.updated_at,
    })),
  );
}

export function fetchSandboxMessages(conversationId: string) {
  return apiFetch<{ status: 'ok'; messages: ChatHistoryMessage[] }>(
    ENDPOINTS.sandboxConversationMessages(conversationId),
    { method: 'GET' },
  );
}

/** Throw the test conversations away. Probing an escalation path should not
 *  leave a reviewer living with it at the top of their list. */
export function resetSandbox() {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.sandboxReset, { method: 'POST' });
}
