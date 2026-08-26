/**
 * Home — the conversation (redesign change 3, mockup screen 05).
 *
 * Before: a nine-tool grid plus a DUE TODAY strip, where every capability was
 * a door the patient had to know to open. After: home IS the conversation.
 * The header carries the wordmark and the lifecycle stage as quiet italic
 * words (never a number, never a progress bar); the composer's "+" holds
 * exactly three tools; everything else arrives as a card Sage deals into the
 * stream at the moment it is relevant.
 *
 * Home continues the most recent thread rather than starting a fresh one each
 * launch — the conversation is the product, and it should still be there
 * tomorrow. Older threads live in the drawer's Recents.
 *
 * Kept: the left-edge swipe for the drawer, the consent gate on the composer,
 * and the anchor question — now dealt as a card instead of owning a whole
 * screen mode.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { APP_NAME } from '@shared/branding';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { ScanLine } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { runOnJS } from 'react-native-reanimated';

import { ConversationSurface } from '@/components/chat/ConversationSurface';
import { CardChip, DealtCard } from '@/components/chat/DealtCard';
import { LIFECYCLE_LABELS } from '@/components/common/LifecycleStageLine';
import { useNavOverlay } from '@/components/common/NavOverlay';
import { TopBar } from '@/components/common/TopBar';
import { Colors, FontSize, Fonts, Spacing } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useHero, useProfile } from '@/hooks/useCare';
import { NEW_CONVERSATION } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';
import { logCardEvent } from '@/lib/api/cards';
import { fetchCancerOptions, updateCancerSlug } from '@/lib/api/care';
import { fetchConsentStatus } from '@/lib/api/consent';
import { usePerspective } from '@/lib/perspective';

const STILL_FINDING_KEY = 'sage:still_finding_out';
const SCAN_CARD_KEY = 'sage:scan_card_dismissed';

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

/** A dismissed card stays dismissed — "Not now" has to mean it. */
function useDismissed(key: string) {
  const [state, setState] = useState<boolean | null>(null);
  useEffect(() => {
    AsyncStorage.getItem(key)
      .then((v) => setState(v === '1'))
      .catch(() => setState(false));
  }, [key]);
  const dismiss = () => {
    setState(true);
    AsyncStorage.setItem(key, '1').catch(() => {});
  };
  return { dismissed: state, dismiss };
}

export default function HomeScreen() {
  const who = usePerspective();
  const ack = useAcknowledgement();
  const profile = useProfile();
  const hero = useHero();
  const qc = useQueryClient();
  const { conversations } = useConversations();

  const { stillFinding, mark: markStillFinding } = useStillFindingOut();
  const scanCard = useDismissed(SCAN_CARD_KEY);

  const consentStatus = useQuery({ queryKey: ['consent-status'], queryFn: fetchConsentStatus });
  const chatDisabled = consentStatus.data?.chat_disabled ?? false;

  const needsCancerPick = (ack.data?.needs_cancer_pick ?? false) && stillFinding === false;

  // The anchor card needs the pickable cancer list.
  const options = useQuery({
    queryKey: ['cancer-options'],
    queryFn: () => fetchCancerOptions(),
    enabled: needsCancerPick,
    staleTime: 5 * 60_000,
  });
  const pickCancer = useMutation({
    mutationFn: (slug: string) => updateCancerSlug(slug),
    onSuccess: async () => {
      void logCardEvent('anchor_cancer', 'acted');
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      await qc.invalidateQueries({ queryKey: ['profile'] });
    },
  });
  const readyOptions = (options.data?.options ?? []).filter((o) => o.ready);

  // Continue the most recent conversation; a brand-new account starts a new
  // one. Adopting the id the server assigns keeps the composer pointed at the
  // same thread after the first send.
  const [activeId, setActiveId] = useState<string | null>(null);
  const conversationId = activeId ?? conversations[0]?.id ?? NEW_CONVERSATION;

  const { openDrawer } = useNavOverlay();
  const openEdge = Gesture.Pan()
    .activeOffsetX([15, 9999])
    .failOffsetY([-20, 20])
    .onEnd((e) => {
      if (e.translationX > 40 || e.velocityX > 500) runOnJS(openDrawer)();
    });

  const stageLabel = LIFECYCLE_LABELS[profile.data?.lifecycle_stage ?? 'getting_to_know_you'];
  const hasProfile = !!profile.data?.profile;

  // Greet whoever is HOLDING the phone. hero.first_name is the PATIENT's
  // name, which on a caregiver account belongs to someone else entirely:
  // greeting Mary's daughter with "Hi Mary" is the bug this guards.
  const holderName = who.isCaregiver ? who.holderFirstName : hero.data?.first_name;
  const greeting = holderName
    ? `Hi ${holderName}. I'm ${APP_NAME}. ${who.isCaregiver ? "Tell me how they're doing" : "Tell me how you're feeling"}, or ask me anything.`
    : `Hi. I'm ${APP_NAME}. ${who.isCaregiver ? "Tell me how they're doing" : "Tell me how you're feeling"}, or ask me anything.`;

  // Cards Sage deals into the stream. The anchor question comes first when it
  // applies: nothing else is worth asking before Sage knows what this is.
  const cards = (
    <>
      {needsCancerPick && readyOptions.length > 0 && (
        <DealtCard
          kind="anchor_cancer"
          title={
            who.isCaregiver
              ? 'What kind of cancer are they facing?'
              : 'What kind of cancer are you facing?'
          }
          body="If you're not sure, that's okay. We can figure it out together."
          onDismiss={markStillFinding}
          dismissLabel="We're still finding out">
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm }}>
            {readyOptions.slice(0, 6).map((o) => (
              <CardChip
                key={o.slug}
                label={o.short_name}
                disabled={pickCancer.isPending}
                onPress={() => pickCancer.mutate(o.slug)}
              />
            ))}
            <CardChip
              label="Something else"
              onPress={() => router.push('/profile/cancer-switcher')}
            />
          </View>
          {pickCancer.isError ? (
            <Text style={{ fontSize: FontSize.sm, color: Colors.warning }}>
              Could not save that just now. Please try again.
            </Text>
          ) : null}
        </DealtCard>
      )}

      {/* The scanner is the acquisition backbone: it feeds trials, the patient
          model, and "Since your last visit". Offered once Sage knows what this
          is, until it is used or waved off. */}
      {!needsCancerPick && !hasProfile && scanCard.dismissed === false && (
        <DealtCard
          kind="scan_suggestion"
          icon={<ScanLine size={20} color={Colors.primary} />}
          title="Snap a photo of the papers"
          body={`${APP_NAME} will read them and explain what they say in plain words.`}
          actionLabel="Scan them"
          onAction={() => router.push('/tools/report-scan' as never)}
          onDismiss={scanCard.dismiss}
        />
      )}
    </>
  );

  return (
    <View style={{ flex: 1, backgroundColor: Colors.paper }}>
      <TopBar
        leading="menu"
        center={
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: Spacing.sm }}>
            <Text
              style={{
                fontFamily: Fonts.serifSemiBold,
                fontSize: FontSize.h3,
                color: Colors.textPrimary,
              }}>
              {APP_NAME}
            </Text>
            {/* The stage, as quiet words. Never a number, never a bar. */}
            <Text
              numberOfLines={1}
              style={{
                flex: 1,
                fontFamily: Fonts.serifItalic,
                fontSize: FontSize.md,
                color: Colors.textSecondary,
              }}>
              {stageLabel}
            </Text>
          </View>
        }
      />

      <ConversationSurface
        conversationId={conversationId}
        onConversationCreated={(newId) => setActiveId(newId)}
        cards={cards}
        disabled={chatDisabled}
        emptyState={
          <Text
            style={{
              fontFamily: Fonts.serif,
              fontSize: FontSize.xl,
              lineHeight: 26,
              color: Colors.textPrimary,
            }}>
            {greeting}
          </Text>
        }
      />

      {/* Left-edge swipe-to-open-drawer zone. */}
      <GestureDetector gesture={openEdge}>
        <View style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 28 }} />
      </GestureDetector>
    </View>
  );
}
