/**
 * ConversationSurface — the conversation itself, without any chrome.
 *
 * Extracted when Home became the conversation (redesign change 3): Home and
 * the /chat/:id route are the same surface with different headers, and the
 * hard-won parts (silent recovery, the crisis choke point, the select-text
 * sheet, the notify offer, the one-turn-on-disk rule) must not exist twice.
 * Everything below was moved here verbatim from app/(app)/chat/[id].tsx.
 *
 * `cards` renders in-stream under the last message: that is where Sage deals
 * a card, not in a tray beside the conversation.
 */

import { useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, Text, View } from 'react-native';
import Animated, { LinearTransition } from 'react-native-reanimated';

import { BotResponseCard } from '@/components/chat/BotResponseCard';
import { ChatInput } from '@/components/chat/ChatInput';
import { FollowupChips } from '@/components/chat/FollowupChips';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { NotifyOffer } from '@/components/chat/NotifyOffer';
import { SelectTextSheet } from '@/components/chat/SelectTextSheet';
import { SessionMeta } from '@/components/chat/SessionMeta';
import { SourcesSheet } from '@/components/chat/SourcesSheet';
import { TypingIndicator } from '@/components/chat/TypingIndicator';
import { CrisisModal } from '@/components/common/CrisisModal';
import { Duration, Ease, messageEnter } from '@/constants/motion';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { useChat } from '@/hooks/useChat';
import { useGuardedSend } from '@/hooks/useGuardedSend';
import { useModelerTrigger } from '@/hooks/useModelerTrigger';
import { useNotifyOfferSeen } from '@/hooks/useNotifyOfferSeen';
import { useSelectTextHintSeen } from '@/hooks/useSelectTextHintSeen';
import { ApiError, extractErrorMessage } from '@/lib/api/client';
import type { ChatHistoryMessage } from '@shared/types';

export interface CardContext {
  /** The guarded send, so a card can answer INTO the conversation (the
   *  check-in card does exactly that) rather than writing to storage behind
   *  it. Sends made through this do NOT count as the patient speaking. */
  send: (text: string) => void;
  /** A send is already in flight. A card that can fire several in a row must
   *  respect the same one-at-a-time rule as the composer, since only one turn
   *  is remembered on disk for recovery. */
  sending: boolean;
  /** The patient has said something of their own this session — typed it,
   *  tapped a follow-up, or arrived with a question from another screen.
   *  Cards that are UNSOLICITED OFFERS should fold themselves away when this
   *  turns true: an offer that keeps its full size between the question
   *  someone just asked and the answer they are waiting for is an
   *  interruption, however gentle its wording. Cards that are GATES (the name
   *  card, the anchor question) must ignore it — the conversation cannot
   *  proceed without them. */
  patientSpoke: boolean;
}

interface Props {
  conversationId: string;
  onConversationCreated?: (id: string, title?: string | null) => void;
  /** A question handed off from elsewhere (?q=), auto-sent once. */
  autoSend?: string;
  onAutoSendHandled?: () => void;
  /** Composer prefill (never sends) — e.g. "My ZIP code is ". */
  prefill?: string;
  /** Dealt cards, rendered in-stream under the last message. */
  cards?: (ctx: CardContext) => React.ReactNode;
  /** Shown above the composer when the conversation is empty. */
  emptyState?: React.ReactNode;
  disabled?: boolean;
}

export function ConversationSurface({
  conversationId,
  onConversationCreated,
  autoSend,
  onAutoSendHandled,
  prefill,
  cards,
  emptyState,
  disabled,
}: Props) {
  const listRef = useRef<FlatList<ChatHistoryMessage>>(null);
  const lastHandledQ = useRef<string | undefined>(undefined);

  const {
    messages,
    isLoading,
    isSending,
    sendError,
    recovering,
    recoveryFailed,
    pendingQuestion,
    justRecovered,
    clearJustRecovered,
    sendMessage,
  } = useChat(conversationId, { onConversationCreated });

  const { guardedSend, crisis, continueCrisis, closeCrisis } = useGuardedSend(sendMessage);

  // End-of-conversation Modeler ping (Push 2): count sends this session and
  // fire on thread-exit / app-background. Server debounce does the limiting.
  const [sentCount, setSentCount] = useState(0);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  useModelerTrigger(sentCount);

  // ONE sheet for the whole screen, not one per card. `selecting` holds the
  // markdown of whichever message was long-pressed.
  const [selecting, setSelecting] = useState<{ content: string; feedback: boolean } | null>(null);
  const selectHint = useSelectTextHintSeen();
  const notifyOffer = useNotifyOfferSeen();
  const openSelect = (content: string, feedback: boolean) => {
    selectHint.markSeen();
    setSelecting({ content, feedback });
  };
  const sendAndCount = (text: string) => {
    setSentCount((c) => c + 1);
    guardedSend(text);
  };

  // A send the PATIENT initiated, as opposed to a card answering into the
  // conversation on its own behalf. The distinction matters: the check-in
  // card sends every one of its own answers through `sendAndCount`, so
  // counting those would fold the card away after its first question.
  const [patientSpoke, setPatientSpoke] = useState(false);
  const patientSend = (text: string) => {
    setPatientSpoke(true);
    sendAndCount(text);
  };

  // A card inside the thread can fill the composer (the trials ask does),
  // seeded by the `prefill` prop for hand-offs from another screen. The token
  // exists so tapping the same card twice works: the effect in ChatInput keys
  // on the value, and the value does not change.
  const [composerPrefill, setComposerPrefill] = useState<{ text: string; token: number }>({
    text: prefill ?? '',
    token: 0,
  });
  useEffect(() => {
    if (prefill) setComposerPrefill((p) => ({ text: prefill, token: p.token + 1 }));
  }, [prefill]);
  const fillComposer = (text: string) =>
    setComposerPrefill((p) => ({ text, token: p.token + 1 }));

  // ONE scroll owner, not two. This used to be an animated scrollToEnd on a
  // 50ms timeout racing an unanimated one on onContentSizeChange: the list
  // teleported to the bottom the instant a row laid out, and then the new
  // message faded in at a position it had already jumped to. Content size
  // is the right trigger (it fires exactly when new content lands), so the
  // effect is gone and only the ordering question remains: the first layout
  // of an existing thread must not animate through the whole history.
  const settled = useRef(false);
  const onContentSizeChange = () => {
    listRef.current?.scrollToEnd({ animated: settled.current });
    settled.current = true;
  };

  const firstBotIndex = messages.findIndex((m) => m.role === 'assistant');

  // Auto-send a question handed off from elsewhere (?q=).
  useEffect(() => {
    if (!autoSend || isSending) return;
    if (lastHandledQ.current === autoSend) return;
    lastHandledQ.current = autoSend;
    patientSend(autoSend);
    onAutoSendHandled?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSend, isSending]);

  const renderItem = ({ item, index }: { item: ChatHistoryMessage; index: number }) => {
    if (item.role === 'user') {
      return (
        <Animated.View entering={messageEnter()} style={{ paddingHorizontal: 12, paddingVertical: 4 }}>
          <MessageBubble
            role="user"
            content={item.content}
            onSelectText={(c) => openSelect(c, false)}
          />
        </Animated.View>
      );
    }
    const followups = item.metadata?.followups ?? [];
    // Selection lives behind a gesture, and an unadvertised gesture is one
    // nobody finds. Shown once, under the first answer of the thread, until
    // it has actually been used.
    const showHint = selectHint.seen === false && index === firstBotIndex;
    // No thumbs up / thumbs down on a crisis card. Asking someone whether a
    // "call 911" card was helpful is the wrong question at the wrong moment.
    const tier = item.metadata?.safety?.tier;
    const rateable = !tier || tier === 'T3';
    return (
      <Animated.View entering={messageEnter()} style={{ paddingHorizontal: 12, paddingVertical: 6, gap: 8 }}>
        <BotResponseCard
          message={item}
          onPickFollowup={(t) => patientSend(t)}
          onSelectText={(c) => openSelect(c, rateable)}
          onPrefill={fillComposer}
        />
        {showHint && (
          <Text
            style={{
              fontSize: FontSize.xs,
              color: Colors.textMuted,
              fontFamily: Fonts.sans,
              paddingHorizontal: Spacing.xs,
            }}>
            Press and hold any message to copy or select part of it.
          </Text>
        )}
        {/* Outside the card on purpose. These read on the whole thread rather
            than on one answer, and at thread width they have room to wrap
            instead of being clipped mid-question. */}
        {followups.length > 0 && (
          <FollowupChips followups={followups} onPick={(t) => patientSend(t)} />
        )}
      </Animated.View>
    );
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      {/* PINNED, not a list header. This is the per-session AI disclosure
          three state laws require (see SessionMeta), and Home now opens
          into an existing conversation and scrolls straight to the bottom,
          so as a header it was auto-scrolled out of sight every launch. */}
      <SessionMeta />
      <FlatList
        ref={listRef}
        data={messages}
        renderItem={renderItem}
        // Server row id first. Keying on created_at alone meant a recovery
        // refetch (server timestamps, not the client's optimistic ones)
        // changed every key at once and remounted the entire thread.
        keyExtractor={(m, i) => m.id ?? `${m.role}-${m.created_at}-${i}`}
        contentContainerStyle={{ paddingVertical: 10 }}
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={onContentSizeChange}
        ListHeaderComponent={
          <View>
            {/* "What is this built on?" is a question about the whole
                conversation, so it sits with the session line rather than
                under each answer or buried in the composer's sheet. */}
            {messages.length > 0 && (
              <Pressable
                onPress={() => setSourcesOpen(true)}
                accessibilityRole="button"
                accessibilityLabel="Sources used in this conversation"
                hitSlop={6}>
                <Text
                  style={{
                    textAlign: 'center',
                    color: Colors.textMuted,
                    fontSize: FontSize.sm,
                    fontFamily: Fonts.sansMedium,
                    paddingVertical: Spacing.xs,
                  }}>
                  Sources used
                </Text>
              </Pressable>
            )}
          </View>
        }
        // Cards are dealt INTO the conversation, under the last thing said.
        ListFooterComponent={
          cards ? (
            <Animated.View
              layout={LinearTransition.duration(Duration.state).easing(Ease.out)}
              style={{ paddingHorizontal: 12, paddingTop: 6, gap: 10 }}>
              {cards({ send: sendAndCount, sending: isSending || recovering, patientSpoke })}
            </Animated.View>
          ) : null
        }
        ListEmptyComponent={
          !isLoading ? (
            <View style={{ paddingHorizontal: 24, paddingTop: 24 }}>{emptyState}</View>
          ) : null
        }
      />

      {isSending && (
        <View style={{ paddingHorizontal: 22, paddingBottom: 2 }}>
          <TypingIndicator />
        </View>
      )}

      {/* Leaving the app mid-question used to come back as a red network
          error, which was simply wrong: the server had finished and filed
          the answer. This says what is actually true. */}
      {!isSending && recovering && (
        <View
          style={{
            marginHorizontal: 12,
            marginBottom: 6,
            padding: 12,
            borderRadius: Radius.md,
            backgroundColor: Colors.surfaceMuted,
            borderWidth: 1,
            borderColor: Colors.border,
          }}>
          <Text style={{ color: Colors.textSecondary, fontSize: FontSize.base, lineHeight: 18 }}>
            <Text style={{ fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
              Still working on your answer.
            </Text>{' '}
            You can close the app. It will be here when you come back.
          </Text>
          {!!pendingQuestion && (
            <Text
              numberOfLines={2}
              style={{
                color: Colors.textMuted,
                fontSize: FontSize.sm,
                marginTop: 4,
                fontStyle: 'italic',
              }}>
              {pendingQuestion}
            </Text>
          )}
        </View>
      )}

      {!isSending && !recovering && (sendError || recoveryFailed) && (
        <View
          accessibilityRole={Platform.OS === 'android' ? 'alert' : undefined}
          style={{
            marginHorizontal: 12,
            marginBottom: 6,
            padding: 12,
            borderRadius: Radius.md,
            backgroundColor: Colors.emergencyBg,
            borderWidth: 1,
            borderColor: Colors.danger,
          }}>
          <Text style={{ color: Colors.textPrimary, fontSize: FontSize.base, lineHeight: 18 }}>
            <Text style={{ fontFamily: Fonts.sansSemiBold, color: Colors.danger }}>
              Couldn&apos;t get a response.
            </Text>{' '}
            {recoveryFailed
              ? 'Your question did not go through. Please try sending it again.'
              : sendError instanceof ApiError
                ? extractErrorMessage(sendError.body, `${sendError.message} (${sendError.status})`)
                : sendError?.message || 'Please try again in a moment.'}
          </Text>
        </View>
      )}

      {/* Asked at the one moment the value is PROVEN rather than predicted:
          they left mid-question and the answer was waiting. iOS gives one
          permission prompt per install, so it is worth spending here and
          nowhere earlier. Shown once, whichever way they answer. */}
      {justRecovered && notifyOffer.seen === false && (
        <NotifyOffer
          onDismiss={() => {
            notifyOffer.markSeen();
            clearJustRecovered();
          }}
        />
      )}

      <ChatInput
        onSend={patientSend}
        // Also held while recovering: only one turn is remembered on disk, so
        // a second question would overwrite the one still being collected.
        disabled={disabled || isSending || recovering}
        prefill={composerPrefill.text}
        prefillToken={composerPrefill.token}
      />

      <SourcesSheet open={sourcesOpen} onClose={() => setSourcesOpen(false)} messages={messages} />

      <SelectTextSheet
        content={selecting?.content ?? null}
        onClose={() => setSelecting(null)}
        showFeedback={selecting?.feedback ?? false}
      />

      <CrisisModal category={crisis?.hit.category ?? null} onContinue={continueCrisis} onClose={closeCrisis} />
    </KeyboardAvoidingView>
  );
}
