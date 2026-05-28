import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, router } from 'expo-router';
import { Trash2 } from 'lucide-react-native';
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
import { ProfileNudgeBanner } from '@/components/chat/ProfileNudgeBanner';
import { QuickPrompts } from '@/components/chat/QuickPrompts';
import { SessionMeta } from '@/components/chat/SessionMeta';
import { WelcomeProfileModal } from '@/components/chat/WelcomeProfileModal';
import { CrisisModal } from '@/components/common/CrisisModal';
import { Colors, Fonts } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useChat } from '@/hooks/useChat';
import { useProfile } from '@/hooks/useCare';
import { useWelcomePromptSeen } from '@/hooks/useWelcomePromptSeen';
import { fetchConsentStatus } from '@/lib/api/consent';
import { scanForCrisis, type GuardrailHit } from '@/lib/safety/crisis-keywords';
import { Sentry } from '@/lib/sentry';
import { welcomeIntroFor } from '@shared/disclaimers';
import type { ChatHistoryMessage } from '@shared/types';

export default function ChatScreen() {
  const { messages, isLoading, isSending, sendMessage, clearAll } = useChat();
  const ack = useAcknowledgement();
  const profile = useProfile();
  const listRef = useRef<FlatList<ChatHistoryMessage>>(null);
  const params = useLocalSearchParams<{ q?: string }>();
  const lastHandledQ = useRef<string | undefined>(undefined);
  const [crisis, setCrisis] = useState<{ hit: GuardrailHit; pending: string } | null>(null);

  // Persistent nudge — banner stays on the chat screen until the user
  // actually has a patient profile saved.
  const hasProfile = !!profile.data?.profile;
  const showProfileNudge = !profile.isLoading && !hasProfile;

  // First-launch welcome modal — fires the FIRST time a profile-less user
  // lands here. Once they action it (build profile or dismiss), it never
  // shows again on this device; the persistent banner above keeps nudging.
  const welcomePrompt = useWelcomePromptSeen();
  const welcomeOpen = welcomePrompt.seen === false && showProfileNudge;

  // Consent gate. If the user withdrew collection or sharing consent we
  // can't process /api/chat — surface a banner and disable the composer.
  // The server also returns HTTP 403 + code:CONSENT_WITHDRAWN, so this
  // is belt-and-suspenders against a stale fetch.
  const consentStatus = useQuery({
    queryKey: ['consent-status'],
    queryFn: fetchConsentStatus,
  });
  const chatDisabled = consentStatus.data?.chat_disabled ?? false;
  const withdrawnKey = consentStatus.data
    ? !consentStatus.data.consent_collection.granted
      ? 'data collection'
      : !consentStatus.data.consent_sharing.granted
        ? 'AI provider sharing'
        : null
    : null;

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
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          paddingHorizontal: 16,
          paddingTop: 10,
          paddingBottom: 12,
          borderBottomWidth: 1,
          borderBottomColor: Colors.border,
        }}>
        <Text
          style={{
            fontFamily: Fonts.serifBold,
            fontSize: 22,
            color: Colors.textPrimary,
          }}>
          WondrChat
        </Text>

        <View style={{ flex: 1 }} />

        {messages.length > 0 && (
          <Pressable
            onPress={handleClear}
            accessibilityRole="button"
            accessibilityLabel="Clear conversation"
            hitSlop={8}
            style={({ pressed }) => ({
              width: 36,
              height: 36,
              borderRadius: 18,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: pressed ? Colors.sidebarBg : 'transparent',
              marginLeft: 6,
            })}>
            <Trash2 size={20} color={Colors.textMuted} />
          </Pressable>
        )}
      </View>

      {showProfileNudge && (
        <ProfileNudgeBanner onPress={() => router.push('/profile/build')} />
      )}

      {chatDisabled && (
        <View
          accessibilityRole={Platform.OS === 'android' ? 'alert' : undefined}
          style={{
            margin: 12,
            padding: 12,
            borderRadius: 10,
            backgroundColor: Colors.warningBg,
            borderWidth: 1,
            borderColor: Colors.warning,
          }}>
          <Text style={{ color: Colors.textPrimary, fontSize: 13, lineHeight: 18 }}>
            <Text style={{ fontFamily: Fonts.serifBold }}>Chat is disabled.</Text>{' '}
            You've withdrawn consent for {withdrawnKey ?? 'one or more processing categories'}.{' '}
            Re-enable it in <Text style={{ fontFamily: Fonts.sansSemiBold }}>Settings → Consent Management</Text>.
          </Text>
          <Pressable
            onPress={() => router.push('/settings/consent-management')}
            accessibilityRole="button"
            accessibilityLabel="Open Consent Management"
            style={{ marginTop: 8 }}>
            <Text style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 13 }}>
              Open Consent Management →
            </Text>
          </Pressable>
        </View>
      )}

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
          ListHeaderComponent={<SessionMeta />}
          ListEmptyComponent={
            !isLoading ? (
              <View
                style={{
                  paddingHorizontal: 24,
                  paddingTop: 24,
                  paddingBottom: 8,
                  gap: 8,
                  alignItems: 'center',
                }}>
                <Text
                  style={{
                    fontFamily: Fonts.serifBold,
                    fontSize: 26,
                    color: Colors.textPrimary,
                    lineHeight: 32,
                    textAlign: 'center',
                  }}>
                  Welcome
                </Text>
                <Text
                  style={{
                    color: Colors.textSecondary,
                    fontSize: 15,
                    lineHeight: 22,
                    textAlign: 'center',
                  }}>
                  {welcomeIntroFor(ack.data?.cancer_display)}
                </Text>
                <Text
                  style={{
                    color: Colors.textMuted,
                    fontSize: 13,
                    textAlign: 'center',
                    marginTop: 4,
                  }}>
                  Pick a starter below or type your own question.
                </Text>
              </View>
            ) : null
          }
        />

        {isSending && (
          <View style={{ paddingHorizontal: 22, paddingBottom: 2, paddingTop: 0 }}>
            <Text style={{ color: Colors.textMuted, fontSize: 11, fontStyle: 'italic' }}>
              WondrChat is typing…
            </Text>
          </View>
        )}

        {messages.length === 0 && !isSending && !chatDisabled && (
          <QuickPrompts onPick={guardedSend} />
        )}

        <ChatInput
          onSend={guardedSend}
          disabled={isSending || chatDisabled}
          placeholder={
            ack.data?.cancer_display
              ? `Ask about ${ack.data.cancer_display.toLowerCase()}…`
              : 'Ask a question…'
          }
        />
      </KeyboardAvoidingView>

      <CrisisModal
        category={crisis?.hit.category ?? null}
        onContinue={onCrisisContinue}
        onClose={() => setCrisis(null)}
      />

      <WelcomeProfileModal
        visible={welcomeOpen}
        onBuildProfile={() => {
          welcomePrompt.markSeen();
          router.push('/profile/build');
        }}
        onSkip={() => welcomePrompt.markSeen()}
      />
    </SafeAreaView>
  );
}
