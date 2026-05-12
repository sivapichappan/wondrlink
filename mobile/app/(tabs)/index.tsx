import { useQueryClient } from '@tanstack/react-query';
import { Bot, Trash2 } from 'lucide-react-native';
import { useEffect, useRef } from 'react';
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
import { Colors, Fonts } from '@/constants/theme';
import { useChat } from '@/hooks/useChat';
import { AI_DISCLOSURE_BANNER, WELCOME_INTRO } from '@shared/disclaimers';
import type { ChatHistoryMessage } from '@shared/types';

export default function ChatScreen() {
  const { messages, isLoading, isSending, sendMessage, clearAll } = useChat();
  const listRef = useRef<FlatList<ChatHistoryMessage>>(null);
  const qc = useQueryClient();

  useEffect(() => {
    if (messages.length > 0) {
      // small delay so layout settles
      const id = setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
      return () => clearTimeout(id);
    }
  }, [messages.length]);

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
        <BotResponseCard message={item} onPickFollowup={(t) => sendMessage(t)} />
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

        <ChatInput onSend={(t) => sendMessage(t)} disabled={isSending} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
