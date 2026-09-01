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
import { router, useLocalSearchParams } from 'expo-router';
import { ScanLine } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { runOnJS } from 'react-native-reanimated';

import { ConversationSurface, type CardContext } from '@/components/chat/ConversationSurface';
import { CardChip, DealtCard } from '@/components/chat/DealtCard';
import { Bloom } from '@/components/ui/Bloom';
import { ConversationSkeleton } from '@/components/ui/Skeleton';
import { LIFECYCLE_LABELS } from '@/components/common/LifecycleStageLine';
import { useNavOverlay } from '@/components/common/NavOverlay';
import { TopBar } from '@/components/common/TopBar';
import { Colors, FontSize, Fonts, Spacing, Tracking } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useHero, useProfile } from '@/hooks/useCare';
import { NEW_CONVERSATION } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';
import { useReviewerSession } from '@/hooks/useReviewerSession';
import { CheckInCard } from '@/components/chat/CheckInCard';
import { NameCard } from '@/components/chat/NameCard';
import { fetchCheckIn, logCardEvent } from '@/lib/api/cards';
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
  const { conversations, isLoading: conversationsLoading } = useConversations();
  const { isReviewer } = useReviewerSession();

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

  // "New chat" from the drawer or the thread header. Home continues the
  // most recent conversation by default, so starting a fresh one has to be
  // asked for explicitly or the button does nothing at all.
  const params = useLocalSearchParams<{ new?: string }>();
  useEffect(() => {
    if (params.new !== '1') return;
    setActiveId(NEW_CONVERSATION);
    setNameDone((done) => done);
    router.setParams({ new: undefined });
  }, [params.new]);
  // Wait for Recents before deciding. Without the guard the first render
  // resolves to the "new" sentinel, which flashes the empty-state greeting
  // over an existing conversation and, on a fast send, starts a second
  // thread beside the one the person was already in.
  const conversationsReady = !conversationsLoading;
  const conversationId = activeId ?? conversations[0]?.id ?? NEW_CONVERSATION;

  const { openDrawer } = useNavOverlay();
  const openEdge = Gesture.Pan()
    .activeOffsetX([15, 9999])
    .failOffsetY([-20, 20])
    .onEnd((e) => {
      if (e.translationX > 40 || e.velocityX > 500) runOnJS(openDrawer)();
    });

  // The opening question of the conversation (mockup screen 04): the app
  // now starts before it knows what to call anyone.
  const [nameDone, setNameDone] = useState(false);
  const needsName = (ack.data?.needs_basics ?? false) && !nameDone;

  // What Sage would ask right now. Never throws; an unavailable check-in is
  // simply not offered.
  const checkIn = useQuery({
    queryKey: ['check-in'],
    queryFn: fetchCheckIn,
    staleTime: 5 * 60_000,
  });
  const [checkInDone, setCheckInDone] = useState(false);

  const stageLabel = LIFECYCLE_LABELS[profile.data?.lifecycle_stage ?? 'getting_to_know_you'];
  const hasProfile = !!profile.data?.profile;

  // Greet whoever is HOLDING the phone. hero.first_name is the PATIENT's
  // name, which on a caregiver account belongs to someone else entirely:
  // greeting Mary's daughter with "Hi Mary" is the bug this guards.
  const holderName = who.isCaregiver ? who.holderFirstName : hero.data?.first_name;
  const opener = who.isCaregiver ? "Tell me how they're doing" : "Tell me how you're feeling";
  // The name card introduces Sage itself, so the empty state must not do it
  // a second time three lines above ("Hi. I'm Sage." twice on the very
  // first screen).
  const greeting = holderName
    ? `Hi ${holderName}. ${opener}, or ask me anything.`
    : needsName
      ? ''
      : `Hi. I'm ${APP_NAME}. ${opener}, or ask me anything.`;

  // Cards Sage deals into the stream. Order is precedence: the anchor
  // question first (nothing else is worth asking before Sage knows what this
  // is), then the check-in, then the scan suggestion.
  // A reviewer may never hold a patient profile (DB trigger, both
  // directions), so every card here would either fail to save or ask them
  // about a cancer they do not have. Their chat is a sandbox demo.
  //
  // `patientSpoke` separates the GATES from the OFFERS. The name card and the
  // anchor question stay at full size whatever else is happening, because the
  // conversation cannot really proceed without them. The check-in is an offer
  // and folds itself away once she has asked something of her own.
  const cards = isReviewer ? undefined : ({ send, sending, patientSpoke }: CardContext) => (
    <>
      {needsName && (
        // Perspective from the SAME query the gate reads. usePerspective
        // keys on ['acknowledgement'] and useAcknowledgement on
        // ['acknowledgement', userId] — two caches, and the wrong one can
        // still be undefined here, which would file a caregiver as the
        // patient.
        <NameCard
          isCaregiver={ack.data?.perspective === 'caregiver'}
          onDone={() => setNameDone(true)}
        />
      )}

      {!needsName && needsCancerPick && readyOptions.length > 0 && (
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
      {!needsName && !needsCancerPick && !hasProfile && scanCard.dismissed === false && (
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

      {/* The check-in: two or three plain questions from this person's own
          treatment, replacing the six questionnaires. Answers go INTO the
          conversation, so they pass the safety layer like any message. */}
      {!needsName && !needsCancerPick && checkIn.data?.due && !checkInDone && (
        <CheckInCard
          questions={checkIn.data.questions}
          onAnswer={send}
          sending={sending}
          folded={patientSpoke}
          onDone={() => setCheckInDone(true)}
        />
      )}
    </>
  );

  return (
    // The page has a light source now: a soft wash from the top rather than
    // a flat fill. Static, behind everything, no per-frame cost.
    <Bloom>
      <TopBar
        leading="menu"
        center={
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: Spacing.sm }}>
            <Text
              style={{
                fontFamily: Fonts.serifSemiBold,
                fontSize: FontSize.h3,
                letterSpacing: Tracking.title,
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

      {conversationsReady ? (
      <ConversationSurface
        conversationId={conversationId}
        onConversationCreated={(newId) => setActiveId(newId)}
        cards={cards}
        disabled={chatDisabled}
        emptyState={
          greeting ? (
            <Text
              style={{
                fontFamily: Fonts.serif,
                fontSize: FontSize.xl,
                lineHeight: 26,
                color: Colors.textPrimary,
              }}>
              {greeting}
            </Text>
          ) : null
        }
      />
      ) : (
        // Was a blank <View style={{flex:1}} />, so the whole conversation
        // popped in at once after a beat of nothing. A skeleton shaped like
        // a thread says what is coming.
        <ConversationSkeleton />
      )}

      {/* Left-edge swipe-to-open-drawer zone. */}
      <GestureDetector gesture={openEdge}>
        <View style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 28 }} />
      </GestureDetector>
    </Bloom>
  );
}
