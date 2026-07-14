/**
 * Home (design screen 1) — the assistant home, calmer pass.
 *
 * Serif greeting + a care strip derived from REAL signals (due-check-in from
 * days_since_symptom; a second card from last-visit follow-ups — hidden when
 * absent, no fabricated dates), two quick task chips, a short AI-disclosure line
 * (the full verbatim disclosure shows in-thread via SessionMeta), and a bottom
 * composer that hands the first message to a new thread. Crisis guardrail runs
 * in the thread (single choke point).
 */

import { useQuery } from '@tanstack/react-query';
import { router } from 'expo-router';
import { Activity, CalendarClock, ChevronRight, ClipboardList, Microscope } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';

import { ChatInput } from '@/components/chat/ChatInput';
import { ProfileNudgeBanner } from '@/components/chat/ProfileNudgeBanner';
import { WelcomeProfileModal } from '@/components/chat/WelcomeProfileModal';
import { TopBar } from '@/components/common/TopBar';
import { IconCircle } from '@/components/ui/IconCircle';
import { Screen } from '@/components/ui/Screen';
import { SectionLabel } from '@/components/ui/SectionLabel';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { useCareSnapshot, useHero, useProfile } from '@/hooks/useCare';
import { NEW_CONVERSATION } from '@/hooks/useChat';
import { useWelcomePromptSeen } from '@/hooks/useWelcomePromptSeen';
import { fetchConsentStatus } from '@/lib/api/consent';

export default function HomeScreen() {
  const hero = useHero();
  const snap = useCareSnapshot();
  const profile = useProfile();

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
    <Screen
      header={<TopBar leading="menu" />}
      footer={
        <ChatInput onSend={startThread} disabled={chatDisabled} />
      }
      keyboardAvoiding
      gap={Spacing.lg}>
      {showProfileNudge && <ProfileNudgeBanner onPress={() => router.push('/profile/build')} />}

      {/* Greeting */}
      <View style={{ paddingTop: Spacing.xs }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.h1, lineHeight: 36, color: Colors.textPrimary }}>
          {firstName ? `Hi ${firstName},` : 'Hi there,'}
        </Text>
        <Text style={{ fontFamily: Fonts.serif, fontSize: FontSize.h1, lineHeight: 36, color: Colors.textSecondary }}>
          how are you feeling today?
        </Text>
      </View>

      {/* Care strip — derived, hides when no data */}
      {hasStrip && (
        <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
          {checkinDue ? (
            <StripCard tone="accent" label="DUE TODAY" Icon={Activity} title="Wellness check-in" onPress={() => router.push('/tools/screening')} />
          ) : (
            <StripCard label="LATEST CHECK-IN" Icon={Activity} title={days === 0 ? 'Today' : `${days}d ago`} onPress={() => router.push('/care')} />
          )}
          {pendingFollowups > 0 ? (
            <StripCard label="FROM LAST VISIT" Icon={CalendarClock} title={`${pendingFollowups} follow-up${pendingFollowups > 1 ? 's' : ''}`} onPress={() => router.push('/tools/previsit')} />
          ) : lastVisitPretty ? (
            <StripCard label="LAST VISIT" Icon={CalendarClock} title={lastVisitPretty} onPress={() => router.push('/care')} />
          ) : (
            <View style={{ flex: 1 }} />
          )}
        </View>
      )}

      {/* Two quick task chips */}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }}>
        <SectionLabel>Get something done</SectionLabel>
        <View style={{ flex: 1, height: 1, backgroundColor: Colors.border }} />
        <Pressable onPress={() => router.push('/tools')} accessibilityRole="button" accessibilityLabel="All tools" hitSlop={6}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
            <Text style={{ fontSize: FontSize.sm, fontFamily: Fonts.sansSemiBold, color: Colors.primary }}>All tools</Text>
            <ChevronRight size={12} color={Colors.primary} />
          </View>
        </Pressable>
      </View>
      <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
        <Chip Icon={Microscope} label="Find trials" onPress={() => router.push('/tools/clinical-trials')} />
        <Chip Icon={ClipboardList} label="Pre-visit questions" onPress={() => router.push('/tools/previsit')} />
      </View>

      {/* Discreet AI note — full verbatim disclosure lands in-thread via SessionMeta. */}
      <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted, textAlign: 'center' }}>
        AI support tool · not medical advice
      </Text>

      <WelcomeProfileModal
        visible={welcomeOpen}
        onBuildProfile={() => {
          welcomePrompt.markSeen();
          router.push('/profile/build');
        }}
        onSkip={() => welcomePrompt.markSeen()}
      />
    </Screen>
  );
}

function StripCard({ label, title, Icon, tone, onPress }: { label: string; title: string; Icon: typeof Activity; tone?: 'accent'; onPress: () => void }) {
  const accent = tone === 'accent';
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={`${label}: ${title}`} style={{ flex: 1 }}>
      <View
        style={{
          borderRadius: Radius.lg,
          padding: Spacing.md,
          gap: Spacing.sm,
          backgroundColor: accent ? Colors.sosBg : Colors.sidebarBg,
          borderWidth: accent ? 1 : 0,
          borderColor: accent ? Colors.sosBorder : 'transparent',
        }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Icon size={15} color={accent ? Colors.warning : Colors.primary} />
          <Text style={{ fontSize: FontSize.xs, fontFamily: Fonts.sansSemiBold, letterSpacing: 0.4, color: accent ? Colors.warning : Colors.textMuted }}>
            {label}
          </Text>
        </View>
        <Text style={{ fontSize: FontSize.md, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>{title}</Text>
      </View>
    </Pressable>
  );
}

function Chip({ Icon, label, onPress }: { Icon: typeof Activity; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={{ flex: 1 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.lg, backgroundColor: Colors.surfaceMuted, padding: Spacing.md }}>
        <IconCircle size={32} bg={Colors.sidebarBg}>
          <Icon size={16} color={Colors.primary} />
        </IconCircle>
        <Text numberOfLines={1} style={{ flex: 1, fontSize: FontSize.base, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}
