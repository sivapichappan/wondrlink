/**
 * useChat — message state for ONE conversation (multi-conversation model).
 *
 * - conversationId is a real UUID, or the sentinel "new" for an unsaved thread.
 * - Loads display history from /api/conversations/:id/messages (skipped for
 *   "new", which starts empty).
 * - sendMessage: optimistically appends the user bubble, POSTs /api/chat with
 *   conversation_id, appends the assistant bubble with metadata. The SERVER is
 *   the sole writer now — no client-side /api/save_message. When a "new" thread
 *   gets its real id back, the optimistic messages are re-seeded under the real
 *   key and onConversationCreated fires so the screen can swap the route.
 *
 * The legacy single-thread flow (session_id='default', /api/chat_history,
 * /api/save_message) is retired here; those endpoints remain server-side for
 * older installed builds.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import type { ChatHistoryMessage, ChatResponse } from '@shared/types';

import { fetchConversationMessages } from '@/lib/api/conversations';
import { sendChatMessage } from '@/lib/api/chat';
import { CONVERSATIONS_KEY } from './useConversations';
import { useResponseLength } from './useResponseLength';

export const NEW_CONVERSATION = 'new';

function messagesKey(conversationId: string) {
  return ['conversation', conversationId, 'messages'] as const;
}

interface UseChatOptions {
  /** Fires when a "new" thread is assigned a real id by the server. */
  onConversationCreated?: (id: string, title?: string | null) => void;
}

export function useChat(conversationId: string, opts: UseChatOptions = {}) {
  const qc = useQueryClient();
  const { responseLength, setResponseLength } = useResponseLength();
  const key = messagesKey(conversationId);
  const isNew = conversationId === NEW_CONVERSATION;

  const history = useQuery({
    queryKey: key,
    queryFn: () => fetchConversationMessages(conversationId),
    enabled: !isNew,
    staleTime: 30_000,
    // "new" starts empty; optimistic sends populate this cache directly.
    initialData: isNew ? { messages: [] } : undefined,
  });

  const messages: ChatHistoryMessage[] = useMemo(
    () => history.data?.messages ?? [],
    [history.data],
  );

  const send = useMutation({
    mutationFn: async (message: string) => {
      const now = new Date().toISOString();
      const userMsg: ChatHistoryMessage = { role: 'user', content: message, created_at: now };
      qc.setQueryData(key, (prev: { messages: ChatHistoryMessage[] } | undefined) => ({
        messages: [...(prev?.messages ?? []), userMsg],
      }));

      const resp: ChatResponse = await sendChatMessage({
        message,
        response_length: responseLength,
        session_id: conversationId, // legacy field kept for API compatibility
        conversation_id: isNew ? NEW_CONVERSATION : conversationId,
      });

      if (!resp || typeof resp.answer !== 'string' || resp.answer.trim() === '') {
        throw new Error('The server responded but no answer was returned. Please try again.');
      }

      const assistantMsg: ChatHistoryMessage = {
        role: 'assistant',
        content: resp.answer,
        created_at: new Date().toISOString(),
        metadata: {
          sources: resp.sources,
          citations: resp.citations,
          followups: resp.followups,
          resources: resp.resources,
          urgency: resp.urgency,
          clinical_trials: resp.clinical_trials,
          api_used: resp.api_used,
        },
      };
      qc.setQueryData(key, (prev: { messages: ChatHistoryMessage[] } | undefined) => ({
        messages: [...(prev?.messages ?? []), assistantMsg],
      }));

      // A "new" thread just became a real conversation: carry the optimistic
      // messages over to the real key so the route swap doesn't flash empty.
      const newId = resp.conversation_id;
      if (newId && newId !== conversationId) {
        qc.setQueryData(messagesKey(newId), qc.getQueryData(key));
        opts.onConversationCreated?.(newId, resp.title);
      }

      // Recents ordering / title changed.
      qc.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
      return resp;
    },
  });

  return {
    messages,
    isLoading: history.isLoading,
    isSending: send.isPending,
    sendError: send.error,
    sendMessage: (text: string) => send.mutate(text),
    responseLength,
    setResponseLength,
  };
}
