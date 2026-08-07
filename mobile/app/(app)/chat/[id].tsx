/**
 * Chat thread (design screen 2).
 *
 * Reached from Home (first send → /chat/new?q=…), the drawer's Recents
 * (/chat/:id), or New chat (/chat/new). Reuses the existing message components.
 * Every send funnels through useGuardedSend so the crisis guardrail is
 * preserved. When a "new" thread is assigned a real id, we swap the route
 * (cache pre-seeded so there's no empty flash).
 */

import { useLocalSearchParams, router } from 'expo-router';
import { SquarePen } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, Text, View } from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';

import { BotResponseCard } from '@/components/chat/BotResponseCard';
import { ChatInput } from '@/components/chat/ChatInput';
import { FollowupChips } from '@/components/chat/FollowupChips';
import { SelectTextSheet } from '@/components/chat/SelectTextSheet';
import { SourcesSheet } from '@/components/chat/SourcesSheet';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { SessionMeta } from '@/components/chat/SessionMeta';
import { TypingIndicator } from '@/components/chat/TypingIndicator';
import { CrisisModal } from '@/components/common/CrisisModal';
import { TopBar } from '@/components/common/TopBar';
import { Colors, FontSize, Fonts, Spacing } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { NEW_CONVERSATION, useChat } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';
import { useGuardedSend } from '@/hooks/useGuardedSend';
import { useModelerTrigger } from '@/hooks/useModelerTrigger';
import { useSelectTextHintSeen } from '@/hooks/useSelectTextHintSeen';
import { ApiError, extractErrorMessage } from '@/lib/api/client';
import type { ChatHistoryMessage } from '@shared/types';

export default function ChatThreadScreen() {
  const params = useLocalSearchParams<{ id: string; q?: string; prefill?: string }>();
  const id = params.id ?? NEW_CONVERSATION;
  const ack = useAcknowledgement();
  const listRef = useRef<FlatList<ChatHistoryMessage>>(null);
  const lastHandledQ = useRef<string | undefined>(undefined);

  const { conversations } = useConversations();
  const known = conversations.find((c) => c.id === id)?.title;
  const [title, setTitle] = useState<string | undefined>(known);
  useEffect(() => {
    if (known) setTitle(known);
  }, [known]);

  const {
    messages,
    isLoading,
    isSending,
    sendError,
    recovering,
    recoveryFailed,
    pendingQuestion,
    sendMessage,
  } = useChat(id, {
    onConversationCreated: (newId, newTitle) => {
      if (newTitle) setTitle(newTitle);
      // Swap the placeholder route for the real id (cache already seeded).
      router.replace(`/chat/${newId}` as never);
    },
  });

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
  const openSelect = (content: string, feedback: boolean) => {
    selectHint.markSeen();
    setSelecting({ content, feedback });
  };
  const sendAndCount = (text: string) => {
    setSentCount((c) => c + 1);
    guardedSend(text);
  };

  useEffect(() => {
    if (messages.length > 0) {
      const t = setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
      return () => clearTimeout(t);
    }
  }, [messages.length]);

  const firstBotIndex = messages.findIndex((m) => m.role === 'assistant');

  // Auto-send a question handed off from Home / My Care (?q=).
  useEffect(() => {
    const q = params.q;
    if (!q || isSending) return;
    if (lastHandledQ.current === q) return;
    lastHandledQ.current = q;
    sendAndCount(q);
    router.setParams({ q: undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.q, isSending]);

  const renderItem = ({ item, index }: { item: ChatHistoryMessage; index: number }) => {
    if (item.role === 'user') {
      return (
        <Animated.View entering={FadeIn.duration(180)} style={{ paddingHorizontal: 12, paddingVertical: 4 }}>
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
      <Animated.View entering={FadeIn.duration(180)} style={{ paddingHorizontal: 12, paddingVertical: 6, gap: 8 }}>
        <BotResponseCard
          message={item}
          onPickFollowup={(t) => sendAndCount(t)}
          onSelectText={(c) => openSelect(c, rateable)}
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
          <FollowupChips followups={followups} onPick={(t) => sendAndCount(t)} />
        )}
      </Animated.View>
    );
  };

  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      <TopBar
        leading="back"
        backLabel="Home"
        title={title ?? 'New chat'}
        subtitle={ack.data?.cancer_display ?? undefined}
        trailing={
          <Pressable
            // New chat = back to a fresh Home (its composer starts the next
            // thread). This conversation is already saved; it lives in Recents.
            onPress={() => router.navigate('/' as never)}
            accessibilityRole="button"
            accessibilityLabel="New chat"
            hitSlop={8}
            style={{ width: 34, height: 34, alignItems: 'center', justifyContent: 'center' }}>
            <SquarePen size={18} color={Colors.textSecondary} />
          </Pressable>
        }
      />

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <FlatList
          ref={listRef}
          data={messages}
          renderItem={renderItem}
          // Server row id first. Keying on created_at alone meant a recovery
          // refetch (server timestamps, not the client's optimistic ones)
          // changed every key at once and remounted the entire thread.
          keyExtractor={(m, i) => m.id ?? `${m.role}-${m.created_at}-${i}`}
          contentContainerStyle={{ paddingVertical: 10 }}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
          ListHeaderComponent={<SessionMeta />}
          ListEmptyComponent={
            !isLoading ? (
              <View style={{ paddingHorizontal: 24, paddingTop: 40, alignItems: 'center' }}>
                <Text style={{ color: Colors.textMuted, fontSize: 14, textAlign: 'center', fontFamily: Fonts.sans }}>
                  Ask a question to start this conversation.
                </Text>
              </View>
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
              borderRadius: 10,
              backgroundColor: Colors.surfaceMuted,
              borderWidth: 1,
              borderColor: Colors.border,
            }}>
            <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 18 }}>
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
              borderRadius: 10,
              backgroundColor: Colors.emergencyBg,
              borderWidth: 1,
              borderColor: Colors.danger,
            }}>
            <Text style={{ color: Colors.textPrimary, fontSize: 13, lineHeight: 18 }}>
              <Text style={{ fontFamily: Fonts.serifBold, color: Colors.danger }}>Couldn&apos;t get a response.</Text>{' '}
              {recoveryFailed
                ? 'Your question did not go through. Please try sending it again.'
                : sendError instanceof ApiError
                  ? extractErrorMessage(sendError.body, `${sendError.message} (${sendError.status})`)
                  : sendError?.message || 'Please try again in a moment.'}
            </Text>
          </View>
        )}

        <ChatInput
          onSend={sendAndCount}
          // Also held while recovering: only one turn is remembered on disk, so
          // a second question would overwrite the one still being collected.
          disabled={isSending || recovering}
          prefill={params.prefill}
          onSources={() => setSourcesOpen(true)}
        />
      </KeyboardAvoidingView>

      <SourcesSheet open={sourcesOpen} onClose={() => setSourcesOpen(false)} messages={messages} />

      <SelectTextSheet
        content={selecting?.content ?? null}
        onClose={() => setSelecting(null)}
        showFeedback={selecting?.feedback ?? false}
      />

      <CrisisModal category={crisis?.hit.category ?? null} onContinue={continueCrisis} onClose={closeCrisis} />
    </View>
  );
}
