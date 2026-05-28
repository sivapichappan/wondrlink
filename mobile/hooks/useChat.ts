/**
 * useChat — single-session chat state.
 *
 * - Loads /api/chat_history on mount (TanStack Query).
 * - sendMessage: optimistically appends the user message, POSTs /api/chat,
 *   appends the assistant response with all bot-side metadata, then
 *   persists both messages via /api/save_message (fire-and-forget — the UI
 *   is already showing them).
 * - clearAll: DELETE /api/clear_chat, resets the cache.
 *
 * Session id: always 'default' for now (matches the web app). Multi-session
 * support can be added later by parametrizing this hook.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import type { ChatHistoryMessage, ChatResponse } from '@shared/types';

import { clearChatHistory, fetchChatHistory, saveMessage, sendChatMessage } from '@/lib/api/chat';
import { useResponseLength } from './useResponseLength';

const HISTORY_KEY = ['chatHistory', 'default'] as const;
const SESSION_ID = 'default';

export function useChat() {
  const qc = useQueryClient();
  const { responseLength, setResponseLength } = useResponseLength();

  const history = useQuery({
    queryKey: HISTORY_KEY,
    queryFn: () => fetchChatHistory(),
    staleTime: 30_000,
  });

  const messages: ChatHistoryMessage[] = useMemo(() => history.data?.messages ?? [], [history.data]);

  const send = useMutation({
    mutationFn: async (message: string) => {
      // Optimistically add user message
      const now = new Date().toISOString();
      const userMsg: ChatHistoryMessage = { role: 'user', content: message, created_at: now };
      qc.setQueryData(HISTORY_KEY, (prev: { messages: ChatHistoryMessage[] } | undefined) => ({
        messages: [...(prev?.messages ?? []), userMsg],
      }));

      const resp: ChatResponse = await sendChatMessage({
        message,
        response_length: responseLength,
        session_id: SESSION_ID,
      });

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
      qc.setQueryData(HISTORY_KEY, (prev: { messages: ChatHistoryMessage[] } | undefined) => ({
        messages: [...(prev?.messages ?? []), assistantMsg],
      }));

      // Fire-and-forget persistence
      saveMessage({ role: 'user', content: message }).catch(() => {});
      saveMessage({
        role: 'assistant',
        content: resp.answer,
        metadata: assistantMsg.metadata,
      }).catch(() => {});

      return resp;
    },
  });

  const clearAll = useMutation({
    mutationFn: async () => {
      await clearChatHistory();
      qc.setQueryData(HISTORY_KEY, { messages: [] });
    },
  });

  return {
    messages,
    isLoading: history.isLoading,
    isSending: send.isPending,
    sendError: send.error,
    sendMessage: (text: string) => send.mutate(text),
    clearAll: () => clearAll.mutate(),
    responseLength,
    setResponseLength,
  };
}
