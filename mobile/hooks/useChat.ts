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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AppState } from 'react-native';

import type { ChatHistoryMessage, ChatResponse } from '@shared/types';

import { fetchConversationMessages } from '@/lib/api/conversations';
import {
  fetchTurnStatus,
  requestNotifyWhenReady,
  sendChatMessage,
  warmUp,
} from '@/lib/api/chat';
import { fetchSandboxMessages, sendSandboxMessage } from '@/lib/api/sandbox';
import { CONVERSATIONS_KEY } from './useConversations';
import { RECOVERY_DEADLINE_MS, usePendingTurn } from './usePendingTurn';
import { useReviewerSession } from './useReviewerSession';

export const NEW_CONVERSATION = 'new';
const POLL_INTERVAL_MS = 3_000;

function messagesKey(conversationId: string) {
  return ['conversation', conversationId, 'messages'] as const;
}

/**
 * An id for one question, unique enough to be an idempotency key.
 *
 * Deliberately not expo-crypto: that is a native module, and a native module
 * means a full build rather than an OTA update. This is a correlation id, not
 * a secret — the server scopes every lookup by user_id anyway, so the worst a
 * collision can do is 404.
 */
function mintTurnId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

interface UseChatOptions {
  /** Fires when a "new" thread is assigned a real id by the server. */
  onConversationCreated?: (id: string, title?: string | null) => void;
}

export function useChat(conversationId: string, opts: UseChatOptions = {}) {
  const qc = useQueryClient();
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

  // --- Recovering a question the app was backgrounded out of ---
  //
  // The server finishes and writes the answer regardless of whether we are
  // still listening. So a dead socket is not a failure to recover from, it is
  // an answer to go and collect.
  const turn = usePendingTurn();
  const [recovering, setRecovering] = useState(false);
  const [recoveryFailed, setRecoveryFailed] = useState(false);
  const [justRecovered, setJustRecovered] = useState(false);

  const recover = useCallback(async () => {
    const pending = turn.pending;
    if (!pending) return;
    setRecovering(true);
    setRecoveryFailed(false);
    // A backend that has no turn-status endpoint yet is not the same as a
    // question that failed. This ships OTA and can land on phones BEFORE the
    // matching deploy (and would outlive a rollback), and polling a route that
    // does not exist until the deadline would end in "your question did not go
    // through" for a question that went through fine. So consecutive hard
    // failures fall back to simply refreshing the thread: if the answer is
    // there, they see it, which is the honest degradation.
    let consecutiveFailures = 0;
    const refreshThread = async () => {
      const target = pending.conversationId;
      if (target) await qc.invalidateQueries({ queryKey: messagesKey(target) });
      qc.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
      turn.clear();
    };

    try {
      while (Date.now() - pending.startedAt < RECOVERY_DEADLINE_MS) {
        let status;
        try {
          status = await fetchTurnStatus(pending.clientTurnId);
          consecutiveFailures = 0;
        } catch {
          status = null; // transient; the deadline is the real bound
          consecutiveFailures += 1;
          if (consecutiveFailures >= 3) {
            await refreshThread();
            setRecovering(false);
            return;
          }
        }
        if (status?.status === 'answered') {
          const target = status.conversation_id ?? pending.conversationId;
          if (target) {
            // The server is the source of truth here, not the local cache:
            // refetching gets the answer AND repairs the optimistic question
            // that onError rolled back.
            await qc.invalidateQueries({ queryKey: messagesKey(target) });
            qc.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
            if (target !== conversationId) opts.onConversationCreated?.(target, null);
          }
          turn.clear();
          setRecovering(false);
          // They left, came back, and the answer was here. That is the one
          // moment worth spending iOS's single permission prompt on.
          setJustRecovered(true);
          return;
        }
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      }
      // Past the deadline with nothing filed. Now, and only now, is it fair to
      // tell someone their question did not go through.
      setRecoveryFailed(true);
      turn.clear();
    } finally {
      setRecovering(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turn.pending, conversationId, qc]);

  // Two entry points, because there are two ways to come back: the app was
  // suspended and resumed, or it was killed and relaunched into a thread with
  // a pending turn still on disk.
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active' && turn.pending && !send.isPending) void recover();
      // Leaving with a question outstanding is exactly when a nudge is worth
      // having. Best-effort: iOS gives a few seconds here and no promises.
      if (state === 'background' && turn.pending) {
        requestNotifyWhenReady(turn.pending.clientTurnId);
      }
    });
    return () => sub.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turn.pending, recover]);

  const resumedOnce = useRef(false);
  useEffect(() => {
    if (!turn.loaded || resumedOnce.current || !turn.pending) return;
    resumedOnce.current = true;
    void recover();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turn.loaded, turn.pending]);

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

      // Written to disk BEFORE the request, so a kill mid-answer is still
      // recoverable. Reviewers run on the sandbox, which has no chat_turn and
      // no recovery — their session is a demo, not a medical conversation.
      const turnId = mintTurnId();
      if (!isReviewer) {
        turn.begin({
          clientTurnId: turnId,
          conversationId: isNew ? null : conversationId,
          question: message,
          startedAt: Date.now(),
        });
      }

      const send = isReviewer ? sendSandboxMessage : sendChatMessage;
      const resp: ChatResponse = await send({
        message,
        session_id: conversationId, // legacy field kept for API compatibility
        conversation_id: isNew ? NEW_CONVERSATION : conversationId,
        ...(isReviewer ? {} : { client_turn_id: turnId }),
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
          wall: resp.wall,
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
      turn.clear();
      return resp;
    },
    onError: () => {
      // Roll the optimistic question back out. It was written inside
      // mutationFn and never removed, so a failure left a bubble with no
      // answer under it and a retry appended a second copy of the same
      // question. Recovery re-adds it from the server, where it already is.
      qc.setQueryData(key, (prev: { messages: ChatHistoryMessage[] } | undefined) => {
        const list = prev?.messages ?? [];
        const last = list[list.length - 1];
        return last?.role === 'user' ? { messages: list.slice(0, -1) } : { messages: list };
      });
    },
  });

  return {
    messages,
    isLoading: history.isLoading,
    isSending: send.isPending,
    /**
     * Only a real dead end. A lost connection is NOT one: the answer is on the
     * server and `recovering` is going to fetch it, so showing "couldn't get a
     * response" there would be both alarming and untrue.
     */
    sendError: recovering || turn.pending ? null : send.error,
    /** The answer is still coming; the app can be closed. */
    recovering: recovering || (!!turn.pending && !send.isPending),
    /** Deadline passed with nothing filed. This one really did fail. */
    recoveryFailed,
    /** What was asked, for showing while a cold start recovers it. */
    pendingQuestion: turn.pending?.question ?? null,
    /** A recovery just succeeded: they left and the answer was here on return.
     *  The only moment worth spending iOS's one permission prompt on. */
    justRecovered,
    clearJustRecovered: () => setJustRecovered(false),
    sendMessage: (text: string) => send.mutate(text),
  };
}
