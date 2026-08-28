/**
 * Chat thread — a past conversation opened from the drawer's Recents.
 *
 * Home IS the conversation now (redesign change 3), so this route is the
 * way back into an older thread rather than the only place chat happens.
 * The surface itself lives in ConversationSurface, shared with Home; this
 * file is only the chrome around it.
 */

import { useLocalSearchParams, router } from 'expo-router';
import { SquarePen } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { ConversationSurface } from '@/components/chat/ConversationSurface';
import { Bloom } from '@/components/ui/Bloom';
import { TopBar } from '@/components/common/TopBar';
import { Colors, FontSize, Fonts } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { NEW_CONVERSATION } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';

export default function ChatThreadScreen() {
  const params = useLocalSearchParams<{ id: string; q?: string; prefill?: string }>();
  const id = params.id ?? NEW_CONVERSATION;
  const ack = useAcknowledgement();

  const { conversations } = useConversations();
  const known = conversations.find((c) => c.id === id)?.title;
  const [title, setTitle] = useState<string | undefined>(known);
  useEffect(() => {
    if (known) setTitle(known);
  }, [known]);

  return (
    <Bloom>
      <TopBar
        leading="back"
        backLabel="Home"
        title={title ?? 'New chat'}
        subtitle={ack.data?.cancer_display ?? undefined}
        trailing={
          <Pressable
            // New chat = Home, told to start a fresh thread (Home
            // continues the most recent one otherwise). This thread is
            // already saved; it lives in Recents.
            onPress={() => router.navigate('/?new=1' as never)}
            accessibilityRole="button"
            accessibilityLabel="New chat"
            hitSlop={8}
            style={{ width: 34, height: 34, alignItems: 'center', justifyContent: 'center' }}>
            <SquarePen size={18} color={Colors.textSecondary} />
          </Pressable>
        }
      />

      <ConversationSurface
        conversationId={id}
        onConversationCreated={(newId, newTitle) => {
          if (newTitle) setTitle(newTitle);
          // Swap the placeholder route for the real id (cache already seeded).
          router.replace(`/chat/${newId}` as never);
        }}
        autoSend={params.q}
        onAutoSendHandled={() => router.setParams({ q: undefined })}
        prefill={params.prefill}
        emptyState={
          <Text
            style={{
              color: Colors.textMuted,
              fontSize: FontSize.md,
              textAlign: 'center',
              fontFamily: Fonts.sans,
            }}>
            Ask a question to start this conversation.
          </Text>
        }
      />
    </Bloom>
  );
}
