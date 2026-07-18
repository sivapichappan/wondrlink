/**
 * Home — Sage's first conversation + permanent home (doc screens 3 / 3b).
 *
 * Two modes:
 *  ANCHOR — no cancer focus picked yet: Sage asks the one question that shapes
 *  everything ("what type of cancer?") right here, chat-style, with chips and
 *  two honest escape hatches ("We're still finding out" reorders the menu and
 *  lets trials wait; "Something else" opens the full picker).
 *  MENU — the personalized capability menu ("Find clinical trials for breast
 *  cancer") plus "or just talk to me" and the composer. Buttons inject an
 *  opening line into chat rather than opening forms.
 *
 * Kept from the previous home: care strip from REAL signals only, left-edge
 * swipe for the drawer, crisis guardrail in-thread (single choke point).
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import {
  Activity,
  CalendarClock,
  FileText,
  MessageCircleQuestion,
  Microscope,
  NotebookPen,
} from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { runOnJS } from 'react-native-reanimated';

import { ChatInput } from '@/components/chat/ChatInput';
import { WelcomeProfileModal } from '@/components/chat/WelcomeProfileModal';
import { useNavOverlay } from '@/components/common/NavOverlay';
import { TopBar } from '@/components/common/TopBar';
import { ListRow } from '@/components/ui/ListRow';
import { IconCircle } from '@/components/ui/IconCircle';
import { Screen } from '@/components/ui/Screen';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useCareSnapshot, useHero, useProfile } from '@/hooks/useCare';
import { NEW_CONVERSATION } from '@/hooks/useChat';
import { useWelcomePromptSeen } from '@/hooks/useWelcomePromptSeen';
import { fetchCancerOptions, updateCancerSlug } from '@/lib/api/care';
import { fetchConsentStatus } from '@/lib/api/consent';

const STILL_FINDING_KEY = 'sage:still_finding_out';

/** "We're still finding out" is remembered so the anchor question doesn't nag. */
function useStillFindingOut() {
  const [state, setState] = useState<boolean | null>(null);
  useEffect(() => {
    AsyncStorage.getItem(STILL_FINDING_KEY)
      .then((v) => setState(v === '1'))
      .catch(() => setState(false));
  }, []);
  const mark = () => {
    setState(true);
    AsyncStorage.setItem(STILL_FINDING_KEY, '1').catch(() => {});
  };
  return { stillFinding: state, mark };
}

export default function HomeScreen() {
  const hero = useHero();
  const snap = useCareSnapshot();
  const profile = useProfile();
  const ack = useAcknowledgement();
  const qc = useQueryClient();

  const hasProfile = !!profile.data?.profile;
  const welcomePrompt = useWelcomePromptSeen();
  const { stillFinding, mark: markStillFinding } = useStillFindingOut();

  const consentStatus = useQuery({ queryKey: ['consent-status'], queryFn: fetchConsentStatus });
  const chatDisabled = consentStatus.data?.chat_disabled ?? false;

  const cancerDisplay = ack.data?.cancer_display ?? null;
  const needsCancerPick = (ack.data?.needs_cancer_pick ?? false) && stillFinding === false;
  const anchorMode = needsCancerPick && !ack.isLoading;

  // Anchor mode needs the pickable cancer list.
  const options = useQuery({
    queryKey: ['cancer-options'],
    queryFn: () => fetchCancerOptions(),
    enabled: anchorMode,
    staleTime: 5 * 60_000,
  });
  const pickCancer = useMutation({
    mutationFn: (slug: string) => updateCancerSlug(slug),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      await qc.invalidateQueries({ queryKey: ['profile'] });
    },
  });

  const welcomeOpen = welcomePrompt.seen === false && !hasProfile && !profile.isLoading && !anchorMode;

  const firstName = hero.data?.first_name;
  const days = snap.data?.days_since_symptom;
  const checkinDue = days == null || days >= 7;
  const pendingFollowups = hero.data?.last_visit?.pending_followups ?? 0;
  const lastVisitPretty = hero.data?.last_visit?.when_pretty;
  const hasStrip = !anchorMode && (checkinDue || pendingFollowups > 0 || !!lastVisitPretty);

  const { openDrawer } = useNavOverlay();

  const startThread = (text: string) => {
    router.push(`/chat/${NEW_CONVERSATION}?q=${encodeURIComponent(text)}` as never);
  };
  const prefillThread = (text: string) => {
    router.push(`/chat/${NEW_CONVERSATION}?prefill=${encodeURIComponent(text)}` as never);
  };

  const openEdge = Gesture.Pan()
    .activeOffsetX([15, 9999])
    .failOffsetY([-20, 20])
    .onEnd((e) => {
      if (e.translationX > 40 || e.velocityX > 500) runOnJS(openDrawer)();
    });

  const readyOptions = (options.data?.options ?? []).filter((o) => o.ready);

  return (
    <View style={{ flex: 1 }}>
      <Screen
        header={<TopBar leading="menu" />}
        footer={<ChatInput onSend={startThread} disabled={chatDisabled} />}
        keyboardAvoiding
        gap={Spacing.lg}>
        {/* Greeting */}
        <View style={{ paddingTop: Spacing.xs }}>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.h1, lineHeight: 36, color: Colors.textPrimary }}>
            {firstName ? `Hi ${firstName},` : 'Hi there,'}
          </Text>
          <Text style={{ fontFamily: Fonts.serif, fontSize: FontSize.h1, lineHeight: 36, color: Colors.textSecondary }}>
            {anchorMode ? "I'm glad you're here." : 'how are you feeling today?'}
          </Text>
        </View>

        {anchorMode ? (
          /* ---- First conversation: the anchor question ---- */
          <View style={{ gap: Spacing.md }}>
            <View
              style={{
                backgroundColor: Colors.surfaceMuted,
                borderRadius: Radius.lg,
                padding: Spacing.lg,
              }}>
              <Text style={{ fontSize: FontSize.lg, lineHeight: 23, color: Colors.textPrimary }}>
                To help you best, can I ask: what type of cancer are you facing?
              </Text>
            </View>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm }}>
              {readyOptions.slice(0, 6).map((o) => (
                <Pressable
                  key={o.slug}
                  disabled={pickCancer.isPending}
                  onPress={() => pickCancer.mutate(o.slug)}
                  accessibilityRole="button"
                  accessibilityLabel={o.display_name}>
                  <View
                    style={{
                      paddingHorizontal: 14,
                      paddingVertical: 9,
                      borderRadius: Radius.pill,
                      borderWidth: 1,
                      borderColor: Colors.border,
                      backgroundColor: Colors.surface,
                      opacity: pickCancer.isPending ? 0.5 : 1,
                    }}>
                    <Text style={{ fontSize: FontSize.base, color: Colors.textPrimary }}>{o.short_name}</Text>
                  </View>
                </Pressable>
              ))}
              <Pressable
                onPress={() => router.push('/profile/cancer-switcher')}
                accessibilityRole="button"
                accessibilityLabel="Something else">
                <View
                  style={{
                    paddingHorizontal: 14,
                    paddingVertical: 9,
                    borderRadius: Radius.pill,
                    borderWidth: 1,
                    borderColor: Colors.primary,
                    backgroundColor: Colors.primarySoft,
                  }}>
                  <Text style={{ fontSize: FontSize.base, color: Colors.primaryPressed }}>Something else</Text>
                </View>
              </Pressable>
            </View>
            <Pressable onPress={markStillFinding} accessibilityRole="button" accessibilityLabel="We're still finding out">
              <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted, paddingVertical: 4 }}>
                We&apos;re still finding out
              </Text>
            </Pressable>
            {pickCancer.isError ? (
              <Text style={{ fontSize: FontSize.sm, color: Colors.warning }}>
                Could not save that just now. Please try again.
              </Text>
            ) : null}
          </View>
        ) : (
          /* ---- Permanent home: the capability menu ---- */
          <View style={{ gap: Spacing.md }}>
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

            <Text style={{ fontSize: FontSize.md, color: Colors.textSecondary }}>
              Here is how I can help:
            </Text>
            <View style={{ gap: Spacing.sm }}>
              <MenuRow
                Icon={NotebookPen}
                title="Sum up a doctor visit"
                subtitle="Turn visit notes into plain words and next steps"
                onPress={() => router.push('/tools/visit-recap')}
              />
              {cancerDisplay ? (
                <MenuRow
                  Icon={Microscope}
                  title={`Find clinical trials for ${cancerDisplay.toLowerCase()}`}
                  subtitle="Matched to you, explained in plain words"
                  onPress={() => router.push('/tools/clinical-trials')}
                />
              ) : (
                <MenuRow
                  Icon={Microscope}
                  title="Set your cancer focus"
                  subtitle="Unlocks trial matching when you are ready"
                  onPress={() => router.push('/profile/cancer-switcher')}
                />
              )}
              <MenuRow
                Icon={MessageCircleQuestion}
                title="Ask about a report or term"
                subtitle="Paste any medical words you want explained"
                onPress={() => prefillThread('Can you explain what this means: ')}
              />
              <MenuRow
                Icon={FileText}
                title="Add my medical details"
                subtitle="A short optional form for a head start"
                onPress={() => router.push('/profile/build')}
              />
            </View>
            <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted }}>
              Or just talk to me. Ask anything, anytime.
            </Text>
          </View>
        )}

        {/* Discreet AI note — full verbatim disclosure lands in-thread via SessionMeta. */}
        <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted, textAlign: 'center', marginTop: 'auto' }}>
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
      {/* Left-edge swipe-to-open-drawer zone. */}
      <GestureDetector gesture={openEdge}>
        <View style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 28 }} />
      </GestureDetector>
    </View>
  );
}

function MenuRow({
  Icon,
  title,
  subtitle,
  onPress,
}: {
  Icon: typeof Activity;
  title: string;
  subtitle: string;
  onPress: () => void;
}) {
  return (
    <ListRow
      icon={
        <IconCircle size={34} bg={Colors.sidebarBg}>
          <Icon size={17} color={Colors.primary} />
        </IconCircle>
      }
      title={title}
      subtitle={subtitle}
      fill="muted"
      onPress={onPress}
      accessibilityLabel={title}
    />
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
