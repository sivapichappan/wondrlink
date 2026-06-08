import { Stack, router } from 'expo-router';
import { Check } from 'lucide-react-native';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { submitPrivacyAppeal } from '@/lib/api/account';
import { CONTACT } from '@shared/disclaimers';
import type { PrivacyAppealType } from '@shared/types';

const TYPES: Array<{ value: PrivacyAppealType; label: string; blurb: string }> = [
  { value: 'access', label: 'Access', blurb: 'I want a copy of my data.' },
  { value: 'deletion', label: 'Deletion', blurb: 'I want my data deleted.' },
  {
    value: 'consent_withdrawal',
    label: 'Consent withdrawal',
    blurb: 'I want to withdraw a previously granted consent.',
  },
  { value: 'other', label: 'Other', blurb: 'Something else — describe below.' },
];

export default function PrivacyAppeal() {
  const [type, setType] = useState<PrivacyAppealType | ''>('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<{ id: string; sla: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!type) {
      setError('Please choose a request type.');
      return;
    }
    if (reason.trim().length < 10) {
      setError('Please describe your request in at least one sentence.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await submitPrivacyAppeal({ request_type: type, reason: reason.trim() });
      setSuccess({ id: res.appeal_id, sla: res.sla_due });
    } catch (e) {
      setError(e instanceof ApiError ? e.body?.error ?? 'Could not submit.' : 'Could not submit.');
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
        <Stack.Screen options={{ title: 'Appeal submitted' }} />
        <ScrollView contentContainerStyle={{ padding: 20, gap: 14 }}>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 20, color: Colors.textPrimary }}>
            We received your appeal
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
            Reference: <Text style={{ fontFamily: Fonts.sansSemiBold }}>{success.id}</Text>
            {'\n\n'}We will respond within 45 days (due by {success.sla.split('T')[0]}). If you
            don't hear from us by that date, please email {CONTACT.appeals}.
          </Text>
          <Button label="Back to Settings" fullWidth size="lg" onPress={() => router.back()} />
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Privacy appeal' }} />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            Submit a formal privacy request. We respond within 45 days per the Washington My
            Health My Data Act standard, extended to all users.
          </Text>

          <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 14, color: Colors.textPrimary }}>
            Request type
          </Text>
          <View style={{ gap: 6 }}>
            {TYPES.map((t) => {
              const selected = type === t.value;
              return (
                <Pressable
                  key={t.value}
                  onPress={() => setType(t.value)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected }}
                  style={({ pressed }) => ({
                    padding: 12,
                    borderRadius: Radius.md,
                    borderWidth: selected ? 2 : 1,
                    borderColor: selected ? Colors.primary : Colors.border,
                    backgroundColor: selected
                      ? Colors.primarySoft
                      : pressed
                        ? Colors.surfaceMuted
                        : Colors.surface,
                  })}>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <Text
                        style={{
                          color: selected ? Colors.primary : Colors.textPrimary,
                          fontFamily: Fonts.sansSemiBold,
                          fontSize: 14,
                        }}>
                        {t.label}
                      </Text>
                      <Text style={{ color: Colors.textSecondary, fontSize: 12, marginTop: 2 }}>
                        {t.blurb}
                      </Text>
                    </View>
                    {selected && (
                      <Check size={18} color={Colors.primary} style={{ marginLeft: 10 }} />
                    )}
                  </View>
                </Pressable>
              );
            })}
          </View>

          <TextField
            label="Describe your request"
            multiline
            placeholder="Please be as specific as you can."
            value={reason}
            onChangeText={setReason}
            style={{ minHeight: 120, paddingTop: 12, textAlignVertical: 'top' }}
            error={error ?? undefined}
          />

          <Button
            label={submitting ? 'Submitting…' : 'Submit appeal'}
            fullWidth
            size="lg"
            loading={submitting}
            onPress={submit}
          />
          <Button
            label="Cancel"
            variant="ghost"
            fullWidth
            onPress={() => router.back()}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
