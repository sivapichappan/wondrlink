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
import { useEffect, useMemo, useRef } from 'react';

import type { ChatHistoryMessage, ChatResponse } from '@shared/types';

import { fetchConversationMessages } from '@/lib/api/conversations';
import { sendChatMessage, warmUp } from '@/lib/api/chat';
import { fetchSandboxMessages, sendSandboxMessage } from '@/lib/api/sandbox';
import { CONVERSATIONS_KEY } from './useConversations';
import { useResponseLength } from './useResponseLength';
import { useReviewerSession } from './useReviewerSession';

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

  // A reviewer's chat runs on a synthetic patient in separate tables (§5.5).
  // This is the ONE place the app chooses between them: a reviewer may not hold
  // a patient profile, so /api/chat would fail for them anyway — routing here
  // means it fails as an obvious 403 rather than a half-written patient row.
  const { isReviewer } = useReviewerSession();

  const history = useQuery({
    queryKey: key,
    queryFn: () =>
      isReviewer ? fetchSandboxMessages(conversationId) : fetchConversationMessages(conversationId),
    enabled: !isNew,
    staleTime: 30_000,
    // "new" starts empty; optimistic sends populate this cache directly.
    initialData: isNew ? { messages: [] } : undefined,
  });

  const messages: ChatHistoryMessage[] = useMemo(
    () => history.data?.messages ?? [],
    [history.data],
  );

  // Warm the corpus the moment a chat opens, and again once a greeting comes
  // back. The greeting short-circuits before retrieval, so it answers in about
  // a second and tells us nothing about whether the container is ready — and it
  // is very often the FIRST thing someone sends, which makes it the best free
  // warning we get that a real question is seconds away.
  //
  // Fires at most once per mounted conversation. warmUp() never throws and a
  // warm container returns immediately, so the repeat costs nothing.
  const warmed = useRef(false);
  useEffect(() => {
    if (warmed.current) return;
    const lastWasGreeting =
      messages[messages.length - 1]?.metadata?.api_used === 'greeting-shortcircuit';
    if (isNew || messages.length === 0 || lastWasGreeting) {
      warmed.current = true;
      warmUp();
    }
  }, [isNew, messages]);

  const send = useMutation({
    mutationFn: async (message: string) => {
      const now = new Date().toISOString();
      const userMsg: ChatHistoryMessage = { role: 'user', content: message, created_at: now };
      qc.setQueryData(key, (prev: { messages: ChatHistoryMessage[] } | undefined) => ({
        messages: [...(prev?.messages ?? []), userMsg],
      }));

      const send = isReviewer ? sendSandboxMessage : sendChatMessage;
      const resp: ChatResponse = await send({
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
          pending_confirmations: resp.pending_confirmations,
          api_used: resp.api_used,
          is_crisis: resp.is_crisis,
          crisis_resources: resp.crisis_resources,
          crisis_category: resp.crisis_category,
          safety: resp.safety,
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
