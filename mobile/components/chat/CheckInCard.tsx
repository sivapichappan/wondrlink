/**
 * CheckInCard — the check-in, in the conversation (mockup screen 07).
 *
 * Before: "Depression (PHQ-9)" on a tools grid, nine questions with a
 * 0-3 scale each, and a result that read "LATEST PHQ-9: Moderately severe."
 * After: two or three plain questions chosen from this person's own
 * treatment, asked one at a time, answered with a tap.
 *
 * Each tap sends the answer into the conversation as a normal message. That
 * is not a shortcut — it is the design: the answer then passes the frozen
 * safety layer and the belief store exactly like anything else a patient
 * types, which is where PHQ-9 question 9's self-harm detection went when the
 * questionnaire died.
 *
 * "Not now" ends the whole check-in, and the server treats a decline as
 * answered: an escape hatch that asks again tomorrow is a snooze button.
 *
 * ── ON FOLDING WHEN THE PATIENT SPEAKS ────────────────────────────────
 *
 * Reported from a real screen: someone opened the app, typed "I was
 * diagnosed with breast cancer three weeks ago and I don't know what I'm
 * supposed to be doing", and this card sat at full size between her question
 * and the answer she was waiting for, asking about her energy levels.
 *
 * So the card folds itself down to one quiet line the moment she says
 * something of her own. It does NOT vanish and it does NOT record a
 * decline: burning the seven-day cooldown because she happened to have a
 * question first would mean never asking her at all. Tapping the line opens
 * it back up, and once she has opened it deliberately it stays open.
 */

import { useEffect, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react-native';
import { Text, View } from 'react-native';
import Animated, { LinearTransition } from 'react-native-reanimated';

import { CardChip } from '@/components/chat/DealtCard';
import { PressableScale } from '@/components/ui/PressableScale';
import { Duration, Ease, cardEnter, cardExit, messageEnter } from '@/constants/motion';
import { Colors, Elevation, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { logCardEvent, recordCheckIn, type CheckInQuestion } from '@/lib/api/cards';

interface Props {
  questions: CheckInQuestion[];
  /** Sends the answer as a chat message (through the crisis guardrail). */
  onAnswer: (text: string) => void;
  /** The card is finished: answered through, or waved off. */
  onDone: () => void;
  /** A send is already in flight; chips must not queue another. */
  sending?: boolean;
  /** The patient has said something of their own. Folds the card to one
   *  line until they ask for it back. */
  folded?: boolean;
}

/** How many are left, in words, because a digit here reads as a form. */
function remainingLabel(n: number): string {
  const words = ['no', 'one', 'two', 'three', 'four', 'five'];
  const count = words[n] ?? String(n);
  return n === 1 ? 'one question' : `${count} questions`;
}

export function CheckInCard({ questions, onAnswer, onDone, sending, folded }: Props) {
  const [index, setIndex] = useState(0);
  // Sticky: a thing you opened on purpose does not close itself again.
  const [opened, setOpened] = useState(false);
  const logged = useRef(false);
  const asked = useRef<string[]>([]);

  useEffect(() => {
    if (logged.current) return;
    logged.current = true;
    void logCardEvent('check_in', 'shown');
  }, []);

  const question = questions[index];
  if (!question) return null;

  const remaining = questions.length - index;
  const lead =
    index === 0
      ? questions.length === 1
        ? 'Quick check-in, just one question today.'
        : `Quick check-in, just ${questions.length === 2 ? 'two' : 'three'} questions today.`
      : remaining === 1
        ? 'Last one.'
        : null;

  const answer = (chip: string) => {
    // One question at a time, for the same reason the composer holds:
    // only one turn is remembered on disk, so a second send in flight
    // would overwrite the first one's recovery address.
    if (sending) return;
    asked.current = [...asked.current, question.id];
    // The answer carries the question with it, so the thread reads as a
    // conversation rather than a bare "Yes" with no referent.
    onAnswer(`${question.text} ${chip}`);
    const next = index + 1;
    if (next >= questions.length) {
      void logCardEvent('check_in', 'acted');
      void recordCheckIn(asked.current, 'answered');
      onDone();
      return;
    }
    setIndex(next);
  };

  const decline = () => {
    void logCardEvent('check_in', 'dismissed');
    // Everything offered goes on cooldown, not just what was answered.
    void recordCheckIn(questions.map((q) => q.id), 'declined');
    onDone();
  };

  // Folded: one quiet line, out of the way of the conversation she started,
  // still reachable with one tap. Nothing is recorded here — this is not a
  // decline, and treating it as one would cost her the next seven days.
  if (folded && !opened) {
    const label = `Quick check-in · ${remainingLabel(remaining)}`;
    return (
      <Animated.View
        entering={messageEnter()}
        layout={LinearTransition.duration(Duration.state).easing(Ease.out)}>
        <PressableScale
          onPress={() => setOpened(true)}
          accessibilityRole="button"
          accessibilityLabel={`Open the check-in, ${remainingLabel(remaining)}`}
          hitSlop={10}
          style={{ alignSelf: 'flex-start' }}>
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: Spacing.xs,
              paddingVertical: Spacing.xs,
              paddingHorizontal: Spacing.xs,
            }}>
            <Text
              style={{
                color: Colors.textMuted,
                fontSize: FontSize.sm,
                fontFamily: Fonts.sansMedium,
              }}>
              {label}
            </Text>
            <ChevronRight size={14} color={Colors.textMuted} />
          </View>
        </PressableScale>
      </Animated.View>
    );
  }

  return (
    <Animated.View
      entering={cardEnter()}
      exiting={cardExit()}
      layout={LinearTransition.duration(Duration.state).easing(Ease.out)}
      style={{
        backgroundColor: Colors.surface,
        borderWidth: 1,
        borderColor: Colors.accentBorder,
        borderRadius: Radius.lg,
        padding: Spacing.lg,
        gap: Spacing.sm,
        ...Elevation.lifted,
      }}>
      {!!lead && (
        <Text style={{ color: Colors.textSecondary, fontSize: FontSize.md, lineHeight: 21 }}>
          {lead}
        </Text>
      )}

      {/* Sage asking — the serif voice, same as any other thing Sage says.
          Keyed on the question id so moving to the next one crossfades in
          place rather than hard-cutting the text and the whole chip row
          underneath the reader's thumb. */}
      <Animated.View
        key={question.id}
        entering={messageEnter()}
        layout={LinearTransition.duration(Duration.state).easing(Ease.out)}
        style={{ gap: Spacing.sm }}>
        <Text
          style={{
            color: Colors.textPrimary,
            fontFamily: Fonts.serif,
            fontSize: 16,
            lineHeight: 25,
          }}>
          {question.text}
        </Text>

        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginTop: Spacing.xs }}>
          {question.chips.map((chip) => (
            <CardChip key={chip} label={chip} disabled={sending} onPress={() => answer(chip)} />
          ))}
          <CardChip label="Not now" quiet onPress={decline} />
        </View>
      </Animated.View>
    </Animated.View>
  );
}
