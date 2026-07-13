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

import { BotResponseCard } from '@/components/chat/BotResponseCard';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { SessionMeta } from '@/components/chat/SessionMeta';
import { TypingIndicator } from '@/components/chat/TypingIndicator';
import { CrisisModal } from '@/components/common/CrisisModal';
import { TopBar } from '@/components/common/TopBar';
import { Colors, Fonts } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { NEW_CONVERSATION, useChat } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';
import { useGuardedSend } from '@/hooks/useGuardedSend';
import { ApiError, extractErrorMessage } from '@/lib/api/client';
import type { ChatHistoryMessage } from '@shared/types';

export default function ChatThreadScreen() {
  const params = useLocalSearchParams<{ id: string; q?: string }>();
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

  const { messages, isLoading, isSending, sendError, sendMessage } = useChat(id, {
    onConversationCreated: (newId, newTitle) => {
      if (newTitle) setTitle(newTitle);
      // Swap the placeholder route for the real id (cache already seeded).
      router.replace(`/chat/${newId}` as never);
    },
  });

  const { guardedSend, crisis, continueCrisis, closeCrisis } = useGuardedSend(sendMessage);

  useEffect(() => {
    if (messages.length > 0) {
      const t = setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
      return () => clearTimeout(t);
    }
  }, [messages.length]);

  // Auto-send a question handed off from Home / My Care (?q=).
  useEffect(() => {
    const q = params.q;
    if (!q || isSending) return;
    if (lastHandledQ.current === q) return;
    lastHandledQ.current = q;
    guardedSend(q);
    router.setParams({ q: undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.q, isSending]);

  const renderItem = ({ item }: { item: ChatHistoryMessage }) => {
    if (item.role === 'user') {
      return (
        <View style={{ paddingHorizontal: 12, paddingVertical: 4 }}>
          <MessageBubble role="user" content={item.content} />
        </View>
      );
    }
    return (
      <View style={{ paddingHorizontal: 12, paddingVertical: 6 }}>
        <BotResponseCard message={item} onPickFollowup={(t) => guardedSend(t)} />
      </View>
    );
  };

  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      <TopBar
        leading="back"
        backLabel="Home"
        onBack={() => router.replace('/')}
        title={title ?? 'New chat'}
        subtitle={ack.data?.cancer_display ?? undefined}
        trailing={
          <Pressable
            onPress={() => router.replace(`/chat/${NEW_CONVERSATION}` as never)}
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
          keyExtractor={(m, i) => `${m.created_at}-${i}`}
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

        {!isSending && sendError && (
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
              {sendError instanceof ApiError
                ? extractErrorMessage(sendError.body, `${sendError.message} (${sendError.status})`)
                : sendError.message || 'Please try again in a moment.'}
            </Text>
          </View>
        )}

        <ChatInput
          onSend={guardedSend}
          disabled={isSending}
          placeholder={ack.data?.cancer_display ? `Ask about ${ack.data.cancer_display.toLowerCase()}…` : 'Ask a question…'}
        />
      </KeyboardAvoidingView>

      <CrisisModal category={crisis?.hit.category ?? null} onContinue={continueCrisis} onClose={closeCrisis} />
    </View>
  );
}
