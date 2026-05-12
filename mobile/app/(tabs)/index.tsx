import { useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, router } from 'expo-router';
import { Bot, Trash2 } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BotResponseCard } from '@/components/chat/BotResponseCard';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { CrisisModal } from '@/components/common/CrisisModal';
import { Colors, Fonts } from '@/constants/theme';
import { useChat } from '@/hooks/useChat';
import { scanForCrisis, type GuardrailHit } from '@/lib/safety/crisis-keywords';
import { Sentry } from '@/lib/sentry';
import { AI_DISCLOSURE_BANNER, WELCOME_INTRO } from '@shared/disclaimers';
import type { ChatHistoryMessage } from '@shared/types';

export default function ChatScreen() {
  const { messages, isLoading, isSending, sendMessage, clearAll } = useChat();
  const listRef = useRef<FlatList<ChatHistoryMessage>>(null);
  const qc = useQueryClient();
  const params = useLocalSearchParams<{ q?: string }>();
  const lastHandledQ = useRef<string | undefined>(undefined);
  const [crisis, setCrisis] = useState<{ hit: GuardrailHit; pending: string } | null>(null);

  const guardedSend = (text: string) => {
    const hit = scanForCrisis(text);
    if (hit) {
      setCrisis({ hit, pending: text });
      return;
    }
    sendMessage(text);
  };

  const onCrisisContinue = () => {
    if (!crisis) return;
    Sentry.captureMessage('crisis-guardrail-overridden', {
      level: 'warning',
      tags: { category: crisis.hit.category, matched: crisis.hit.matched },
    });
    const pending = crisis.pending;
    setCrisis(null);
    sendMessage(pending);
  };

  useEffect(() => {
    if (messages.length > 0) {
      // small delay so layout settles
      const id = setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
      return () => clearTimeout(id);
    }
  }, [messages.length]);

  // Auto-send a question passed via ?q= (e.g. from a Care hero suggestion)
  useEffect(() => {
    const q = params.q;
    if (!q || isSending) return;
    if (lastHandledQ.current === q) return;
    lastHandledQ.current = q;
    guardedSend(q);
    // Clear the param so a back-nav doesn't re-trigger
    router.setParams({ q: undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.q, isSending]);

  const handleClear = () => {
    Alert.alert(
      'Clear conversation?',
      'This deletes all messages from this device and your account.',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Clear', style: 'destructive', onPress: () => clearAll() },
      ],
    );
  };

  const renderItem = ({ item }: { item: ChatHistoryMessage }) => {
    if (item.role === 'user') {
      return (
        <View style={{ paddingHorizontal: 12, paddingVertical: 6 }}>
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
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingHorizontal: 16,
          paddingVertical: 10,
          borderBottomWidth: 1,
          borderBottomColor: Colors.border,
        }}>
        <View>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 18, color: Colors.textPrimary }}>
            WondrChat
          </Text>
          <Text style={{ color: Colors.textMuted, fontSize: 11 }}>Your colon cancer guide</Text>
        </View>
        {messages.length > 0 && (
          <Pressable
            onPress={handleClear}
            accessibilityRole="button"
            accessibilityLabel="Clear conversation"
            hitSlop={8}>
            <Trash2 size={18} color={Colors.textMuted} />
          </Pressable>
        )}
      </View>

      <View
        style={{
          flexDirection: 'row',
          gap: 8,
          alignItems: 'flex-start',
          paddingHorizontal: 16,
          paddingVertical: 10,
          backgroundColor: Colors.sidebarBg,
        }}>
        <Bot size={16} color={Colors.primary} />
        <Text
          style={{
            flex: 1,
            color: Colors.textSecondary,
            fontSize: 12,
            lineHeight: 18,
            fontFamily: Fonts.sans,
          }}>
          {AI_DISCLOSURE_BANNER}
        </Text>
      </View>

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
        style={{ flex: 1 }}>
        <FlatList
          ref={listRef}
          data={messages}
          renderItem={renderItem}
          keyExtractor={(m, i) => `${m.created_at}-${i}`}
          contentContainerStyle={{ paddingVertical: 10 }}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
          ListEmptyComponent={
            !isLoading ? (
              <View style={{ padding: 24, gap: 10 }}>
                <Text
                  style={{ fontFamily: Fonts.serifBold, fontSize: 20, color: Colors.textPrimary }}>
                  Welcome
                </Text>
                <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
                  {WELCOME_INTRO}
                </Text>
              </View>
            ) : null
          }
        />

        {isSending && (
          <View
            style={{
              paddingHorizontal: 22,
              paddingBottom: 4,
            }}>
            <Text style={{ color: Colors.textMuted, fontSize: 12, fontStyle: 'italic' }}>
              WondrChat is typing…
            </Text>
          </View>
        )}

        <ChatInput onSend={guardedSend} disabled={isSending} />
      </KeyboardAvoidingView>

      <CrisisModal
        category={crisis?.hit.category ?? null}
        onContinue={onCrisisContinue}
        onClose={() => setCrisis(null)}
      />
    </SafeAreaView>
  );
}
