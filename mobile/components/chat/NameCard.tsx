/**
 * NameCard — "What should I call you?" (mockup screen 04).
 *
 * The last thing the deleted onboarding form asked. It is a card in the
 * conversation now, because a name is something you say to someone, not a
 * field you fill in before you are allowed to start.
 *
 * On a caregiver account the app needs two names and they are not the same
 * person: who is holding the phone, and who this is about. Asking for both
 * here is what keeps every later screen from calling the daughter by her
 * mother's name.
 */

import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Text, TextInput, View } from 'react-native';
import Animated, { LinearTransition } from 'react-native-reanimated';

import { Button } from '@/components/ui/Button';
import { Duration, Ease, cardEnter, cardExit } from '@/constants/motion';
import { Colors, Elevation, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { saveAccountBasics } from '@/lib/api/account';
import { logCardEvent } from '@/lib/api/cards';
import { APP_NAME } from '@shared/branding';

interface Props {
  isCaregiver: boolean;
  onDone: () => void;
}

export function NameCard({ isCaregiver, onDone }: Props) {
  const qc = useQueryClient();
  const [holder, setHolder] = useState('');
  const [patient, setPatient] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logged = useRef(false);

  useEffect(() => {
    if (logged.current) return;
    logged.current = true;
    void logCardEvent('name_ask', 'shown');
  }, []);

  const save = async () => {
    const holderName = holder.trim();
    if (!holderName) {
      setError('Just a first name is plenty.');
      return;
    }
    if (isCaregiver && !patient.trim()) {
      setError("And their first name, so I know who we're talking about.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await saveAccountBasics({
        perspective: isCaregiver ? 'caregiver' : 'self',
        account_holder_name: holderName,
        ...(isCaregiver ? { patient_name: patient.trim() } : {}),
      });
      void logCardEvent('name_ask', 'acted');
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      await qc.invalidateQueries({ queryKey: ['hero'] });
      onDone();
    } catch {
      setError('Could not save that just now. Please try again.');
      setBusy(false);
    }
  };

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
      {/* Sage asking — the serif voice. */}
      <Text
        style={{
          color: Colors.textPrimary,
          fontFamily: Fonts.serif,
          fontSize: 16,
          lineHeight: 25,
        }}>
        {`Hi. I'm ${APP_NAME}. What should I call you?`}
      </Text>

      <Field value={holder} onChange={setHolder} placeholder="Your first name" autoFocus />

      {isCaregiver && (
        <>
          <Text
            style={{
              color: Colors.textPrimary,
              fontFamily: Fonts.serif,
              fontSize: 16,
              lineHeight: 25,
              marginTop: Spacing.xs,
            }}>
            And who are you caring for?
          </Text>
          <Field value={patient} onChange={setPatient} placeholder="Their first name" />
        </>
      )}

      {error ? (
        <Text style={{ fontSize: FontSize.sm, color: Colors.warning }}>{error}</Text>
      ) : null}

      <View style={{ marginTop: Spacing.xs }}>
        <Button label={busy ? 'Saving…' : 'That works'} onPress={save} disabled={busy} />
      </View>

      <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted, lineHeight: 19 }}>
        You can change this any time in Settings.
      </Text>
    </Animated.View>
  );
}

function Field({
  value,
  onChange,
  placeholder,
  autoFocus,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  autoFocus?: boolean;
}) {
  return (
    <TextInput
      value={value}
      onChangeText={onChange}
      placeholder={placeholder}
      placeholderTextColor={Colors.textMuted}
      autoFocus={autoFocus}
      autoCapitalize="words"
      returnKeyType="done"
      maxLength={80}
      style={{
        borderWidth: 1.5,
        borderColor: Colors.border,
        borderRadius: Radius.md,
        paddingHorizontal: Spacing.md,
        paddingVertical: 12,
        fontSize: FontSize.xl,
        fontFamily: Fonts.sans,
        color: Colors.textPrimary,
        backgroundColor: Colors.surface,
      }}
    />
  );
}
