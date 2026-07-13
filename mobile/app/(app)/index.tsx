/**
 * Home (design screen 1) — the assistant home.
 *
 * Serif greeting + a care strip derived from REAL signals (a due-check-in card
 * from days_since_symptom, a second card from last-visit follow-ups — hidden
 * when there's no data, never a fabricated "Next visit" date), a task-chip grid,
 * the verbatim AI disclosure, and a bottom composer that hands the first message
 * off to a new thread (/chat/new?q=…). The crisis guardrail runs in the thread,
 * the single send choke point.
 */

import { useQuery } from '@tanstack/react-query';
import { router } from 'expo-router';
import {
  Activity,
  Bot,
  CalendarClock,
  ChevronRight,
  ClipboardList,
  LineChart,
  Microscope,
  NotebookPen,
} from 'lucide-react-native';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';

import { ChatInput } from '@/components/chat/ChatInput';
import { ProfileNudgeBanner } from '@/components/chat/ProfileNudgeBanner';
import { WelcomeProfileModal } from '@/components/chat/WelcomeProfileModal';
import { TopBar } from '@/components/common/TopBar';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useCareSnapshot, useHero, useProfile } from '@/hooks/useCare';
import { NEW_CONVERSATION } from '@/hooks/useChat';
import { useWelcomePromptSeen } from '@/hooks/useWelcomePromptSeen';
import { fetchConsentStatus } from '@/lib/api/consent';
import { AI_DISCLOSURE_BANNER } from '@shared/disclaimers';

export default function HomeScreen() {
  const hero = useHero();
  const snap = useCareSnapshot();
  const profile = useProfile();
  const ack = useAcknowledgement();

  const hasProfile = !!profile.data?.profile;
  const showProfileNudge = !profile.isLoading && !hasProfile;

  const welcomePrompt = useWelcomePromptSeen();
  const welcomeOpen = welcomePrompt.seen === false && showProfileNudge;

  const consentStatus = useQuery({ queryKey: ['consent-status'], queryFn: fetchConsentStatus });
  const chatDisabled = consentStatus.data?.chat_disabled ?? false;

  const firstName = hero.data?.first_name;
  const days = snap.data?.days_since_symptom;
  const checkinDue = days == null || days >= 7;
  const pendingFollowups = hero.data?.last_visit?.pending_followups ?? 0;
  const lastVisitPretty = hero.data?.last_visit?.when_pretty;

  const startThread = (text: string) => {
    router.push(`/chat/${NEW_CONVERSATION}?q=${encodeURIComponent(text)}` as never);
  };

  const hasStrip = checkinDue || pendingFollowups > 0 || !!lastVisitPretty;

  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      <TopBar leading="menu" showFocusChip />

      {showProfileNudge && <ProfileNudgeBanner onPress={() => router.push('/profile/build')} />}

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }} keyboardShouldPersistTaps="handled">
          {/* Greeting */}
          <View style={{ paddingTop: 6 }}>
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: 28, lineHeight: 36, color: Colors.textPrimary }}>
              {firstName ? `Hi ${firstName} —` : 'Hi —'}
            </Text>
            <Text style={{ fontFamily: Fonts.serif, fontSize: 28, lineHeight: 36, color: Colors.textSecondary }}>
              how are you feeling today?
            </Text>
          </View>

          {/* Care strip (derived, hides when no data) */}
          {hasStrip && (
            <View style={{ flexDirection: 'row', gap: 9 }}>
              {checkinDue ? (
                <StripCard
                  tone="accent"
                  label="DUE TODAY"
                  Icon={Activity}
                  title="Wellness check-in"
                  sub="Takes about 2 minutes"
                  onPress={() => router.push('/tools/screening')}
                />
              ) : (
                <StripCard
                  label="LATEST CHECK-IN"
                  Icon={Activity}
                  title={days === 0 ? 'Today' : `${days}d ago`}
                  sub="Tap to view My Care"
                  onPress={() => router.push('/care')}
                />
              )}
              {pendingFollowups > 0 ? (
                <StripCard
                  label="FROM LAST VISIT"
                  Icon={CalendarClock}
                  title={`${pendingFollowups} follow-up${pendingFollowups > 1 ? 's' : ''}`}
                  sub="Prep pre-visit questions"
                  onPress={() => router.push('/tools/previsit')}
                />
              ) : lastVisitPretty ? (
                <StripCard
                  label="LAST VISIT"
                  Icon={CalendarClock}
                  title={lastVisitPretty}
                  sub="Tap to view My Care"
                  onPress={() => router.push('/care')}
                />
              ) : (
                <View style={{ flex: 1 }} />
              )}
            </View>
          )}

          {/* Task chips */}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 2 }}>
            <Text style={{ fontSize: 10.5, fontFamily: Fonts.sansSemiBold, letterSpacing: 0.6, color: Colors.textMuted }}>
              GET SOMETHING DONE
            </Text>
            <View style={{ flex: 1, height: 1, backgroundColor: Colors.border }} />
            <Pressable onPress={() => router.push('/tools')} accessibilityRole="button" accessibilityLabel="All tools" hitSlop={6}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
                <Text style={{ fontSize: 11.5, fontFamily: Fonts.sansSemiBold, color: Colors.primary }}>All tools</Text>
                <ChevronRight size={12} color={Colors.primary} />
              </View>
            </Pressable>
          </View>

          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 9 }}>
            <Chip Icon={Microscope} label="Find trials" onPress={() => router.push('/tools/clinical-trials')} />
            <Chip Icon={ClipboardList} label="Pre-visit questions" onPress={() => router.push('/tools/previsit')} />
            <Chip Icon={NotebookPen} label="Visit recap" onPress={() => router.push('/tools/visit-recap')} />
            <Chip Icon={LineChart} label="My trends" onPress={() => router.push('/tools/trends')} />
          </View>

          {/* Verbatim AI disclosure */}
          <View
            style={{
              flexDirection: 'row',
              gap: 8,
              alignItems: 'flex-start',
              alignSelf: 'center',
              maxWidth: 360,
              backgroundColor: Colors.sidebarBg,
              borderRadius: Radius.pill,
              paddingVertical: 8,
              paddingHorizontal: 13,
              marginTop: 2,
            }}>
            <Bot size={13} color={Colors.primary} style={{ marginTop: 1 }} />
            <Text style={{ flex: 1, fontSize: 11, lineHeight: 15, color: Colors.textSecondary }}>{AI_DISCLOSURE_BANNER}</Text>
          </View>
        </ScrollView>

        <ChatInput
          onSend={startThread}
          disabled={chatDisabled}
          placeholder={
            ack.data?.cancer_display ? `Ask about ${ack.data.cancer_display.toLowerCase()}, or say how you feel…` : 'Ask anything, or say how you feel…'
          }
        />
      </KeyboardAvoidingView>

      <WelcomeProfileModal
        visible={welcomeOpen}
        onBuildProfile={() => {
          welcomePrompt.markSeen();
          router.push('/profile/build');
        }}
        onSkip={() => welcomePrompt.markSeen()}
      />
    </View>
  );
}

function StripCard({
  label,
  title,
  sub,
  Icon,
  tone,
  onPress,
}: {
  label: string;
  title: string;
  sub: string;
  Icon: typeof Activity;
  tone?: 'accent';
  onPress: () => void;
}) {
  const accent = tone === 'accent';
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`${label}: ${title}`} style={{ flex: 1 }}>
      <View
        style={{
          borderRadius: Radius.lg,
          padding: 12,
          gap: 7,
          backgroundColor: accent ? Colors.sosBg : Colors.sidebarBg,
          borderWidth: accent ? 1 : 0,
          borderColor: accent ? Colors.sosBorder : 'transparent',
        }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Icon size={15} color={accent ? Colors.warning : Colors.primary} />
          <Text style={{ fontSize: 10.5, fontFamily: Fonts.sansSemiBold, letterSpacing: 0.4, color: accent ? Colors.warning : Colors.textMuted }}>
            {label}
          </Text>
        </View>
        <Text style={{ fontSize: 13.5, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary, lineHeight: 18 }}>{title}</Text>
        <Text style={{ fontSize: 12, color: Colors.textSecondary }}>{sub}</Text>
      </View>
    </Pressable>
  );
}

function Chip({ Icon, label, onPress }: { Icon: typeof Activity; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={{ width: '48%' }}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 9,
          borderWidth: 1,
          borderColor: Colors.border,
          borderRadius: Radius.lg,
          backgroundColor: Colors.surfaceMuted,
          padding: 12,
        }}>
        <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: Colors.sidebarBg, alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={16} color={Colors.primary} />
        </View>
        <Text numberOfLines={1} style={{ flex: 1, fontSize: 12.5, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}
