import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Select } from '@/components/ui/Select';
import { Colors, Fonts } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { saveAcknowledgement } from '@/lib/api/consent';
import { logout } from '@/lib/api/auth';
import {
  CONSENT_INTRO,
  CONSENT_LABELS,
} from '@shared/disclaimers';
import { US_STATES, type StateChoice } from '@shared/consent-version';

const stateOptions = [
  ...US_STATES.map((code) => ({ value: code, label: code })),
  { value: 'non_US', label: 'Outside the US' },
];

export default function Consent() {
  const qc = useQueryClient();

  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [state, setState] = useState<StateChoice | ''>('');
  const [collection, setCollection] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [terms, setTerms] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allReady = ageConfirmed && state && collection && sharing && terms;

  const onSubmit = async () => {
    if (!allReady) {
      setError('Please confirm your age, select your state, and accept all three consents.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await saveAcknowledgement({
        age_confirmed: ageConfirmed,
        state: state as StateChoice,
        consent_collection: collection,
        consent_sharing: sharing,
        consent_terms: terms,
      });
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      // Root layout will route to (tabs) on next render.
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        router.replace('/(onboarding)/state-restricted');
        return;
      }
      const msg =
        e instanceof ApiError
          ? e.body?.error ?? `Could not save your acknowledgement (${e.status})`
          : 'Could not save your acknowledgement. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 18 }} keyboardShouldPersistTaps="handled">
        <Text
          style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 20 }}>
          {CONSENT_INTRO}
        </Text>

        <View style={{ height: 1, backgroundColor: Colors.border }} />

        <Checkbox
          label="I am 18 years of age or older"
          checked={ageConfirmed}
          onChange={setAgeConfirmed}
        />

        <Select
          label="State of residence"
          value={state}
          onChange={(v) => setState(v as StateChoice)}
          options={stateOptions}
          placeholder="Select your state…"
        />

        <View style={{ height: 1, backgroundColor: Colors.border, marginVertical: 6 }} />

        <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 14, color: Colors.textPrimary }}>
          Please confirm each consent independently
        </Text>

        <Checkbox
          label={CONSENT_LABELS.consent_collection}
          checked={collection}
          onChange={setCollection}
        />
        <Checkbox label={CONSENT_LABELS.consent_sharing} checked={sharing} onChange={setSharing} />
        <Checkbox
          label={CONSENT_LABELS.consent_terms}
          checked={terms}
          onChange={setTerms}
          description="Includes the Consumer Health Data Privacy Notice."
        />

        <Pressable onPress={() => router.push('/(onboarding)/disclaimer')}>
          <Text style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 13 }}>
            Read the full Consumer Health Data Privacy Notice →
          </Text>
        </Pressable>

        {error && (
          <Text style={{ color: Colors.danger, fontSize: 13, lineHeight: 18 }}>{error}</Text>
        )}

        <View style={{ height: 8 }} />

        <Button
          label="Continue"
          fullWidth
          size="lg"
          loading={submitting}
          disabled={!allReady}
          onPress={onSubmit}
        />
        <Button
          label="Sign out"
          variant="ghost"
          fullWidth
          onPress={async () => {
            await logout();
            await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
          }}
        />
      </ScrollView>
    </SafeAreaView>
  );
}
