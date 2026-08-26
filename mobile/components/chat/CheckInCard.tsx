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
 */

import { useEffect, useRef, useState } from 'react';
import { Text, View } from 'react-native';

import { CardChip } from '@/components/chat/DealtCard';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { logCardEvent, recordCheckIn, type CheckInQuestion } from '@/lib/api/cards';

interface Props {
  questions: CheckInQuestion[];
  /** Sends the answer as a chat message (through the crisis guardrail). */
  onAnswer: (text: string) => void;
  /** The card is finished: answered through, or waved off. */
  onDone: () => void;
  /** A send is already in flight; chips must not queue another. */
  sending?: boolean;
}

export function CheckInCard({ questions, onAnswer, onDone, sending }: Props) {
  const [index, setIndex] = useState(0);
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

  return (
    <View
      style={{
        backgroundColor: Colors.surface,
        borderWidth: 1,
        borderColor: Colors.accentBorder,
        borderRadius: Radius.lg,
        padding: Spacing.lg,
        gap: Spacing.sm,
      }}>
      {!!lead && (
        <Text style={{ color: Colors.textSecondary, fontSize: FontSize.md, lineHeight: 21 }}>
          {lead}
        </Text>
      )}

      {/* Sage asking — the serif voice, same as any other thing Sage says. */}
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
    </View>
  );
}
