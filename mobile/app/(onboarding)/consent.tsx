import DateTimePicker, {
  DateTimePickerEvent,
} from '@react-native-community/datetimepicker';
import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { Calendar, ChevronDown } from 'lucide-react-native';
import { useMemo, useState } from 'react';
import { Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Select } from '@/components/ui/Select';
import { Colors, Fonts } from '@/constants/theme';
import { ApiError, extractErrorMessage } from '@/lib/api/client';
import { saveAcknowledgement } from '@/lib/api/consent';
import { logout } from '@/lib/api/auth';
import {
  CONSENT_INTRO,
  CONSENT_LABELS,
} from '@shared/disclaimers';
import { US_STATES, type StateChoice } from '@shared/consent-version';
import type { AgeBand } from '@shared/types';

const stateOptions = [
  ...US_STATES.map((code) => ({ value: code, label: code })),
  { value: 'non_US', label: 'Outside the US' },
];

// Compute age in completed years from a Date. Mirrors the web JS in
// public/index.html so the client-side gating matches; the server
// re-validates from date_of_birth.
function computeAge(dob: Date): number {
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) age -= 1;
  return age;
}

function ageBandFromAge(age: number): AgeBand | null {
  if (age < 18) return null;
  if (age < 25) return '18-24';
  if (age < 35) return '25-34';
  if (age < 45) return '35-44';
  if (age < 55) return '45-54';
  if (age < 65) return '55-64';
  if (age < 75) return '65-74';
  return '75+';
}

function formatDateInput(d: Date | null): string {
  if (!d) return '';
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

function toIsoDate(d: Date): string {
  // YYYY-MM-DD local-date — no timezone bleed.
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export default function Consent() {
  const qc = useQueryClient();

  // Maximum date the picker will accept = today - 18yr. Default the picker
  // to 30yr ago so the wheels land somewhere sensible.
  const maxDate = useMemo(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 18);
    return d;
  }, []);
  const initialPickerDate = useMemo(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 30);
    return d;
  }, []);

  const [dob, setDob] = useState<Date | null>(null);
  // Open the picker by default — the field is required and easy to miss.
  const [showPicker, setShowPicker] = useState(true);

  const [state, setState] = useState<StateChoice | ''>('');
  const [collection, setCollection] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [terms, setTerms] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const age = dob ? computeAge(dob) : null;
  const isAdult = age != null && age >= 18;
  const allReady = isAdult && state && collection && sharing && terms;

  const onPickerChange = (event: DateTimePickerEvent, selected?: Date) => {
    // iOS keeps the picker open until the user taps Done; Android closes
    // automatically on selection / dismissal.
    if (Platform.OS === 'android') {
      setShowPicker(false);
      if (event.type === 'dismissed') return;
    }
    if (selected) {
      setDob(selected);
      if (computeAge(selected) >= 18) setError(null);
    }
  };

  const onSubmit = async () => {
    if (!allReady) {
      const reasons: string[] = [];
      if (!isAdult) reasons.push('confirm a date of birth (18+)');
      if (!state) reasons.push('select your state');
      if (!collection || !sharing || !terms) reasons.push('accept all three consents');
      setError(`Please ${reasons.join(', ')}.`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const dobIso = dob ? toIsoDate(dob) : undefined;
      const band = age != null ? ageBandFromAge(age) : null;
      await saveAcknowledgement({
        date_of_birth: dobIso,
        age_band: band ?? undefined,
        // Keep age_confirmed=true for back-compat with the legacy validator path.
        age_confirmed: true,
        state: state as StateChoice,
        consent_collection: collection,
        consent_sharing: sharing,
        consent_terms: terms,
      });
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      // Root layout will route to the app home ('/') on next render.
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        router.replace('/(onboarding)/state-restricted');
        return;
      }
      if (e instanceof ApiError && e.status === 451) {
        router.replace('/(onboarding)/region-blocked');
        return;
      }
      const fallback =
        e instanceof ApiError
          ? `Could not save your acknowledgement (${e.status})`
          : 'Could not save your acknowledgement. Please try again.';
      const msg = e instanceof ApiError ? extractErrorMessage(e.body, fallback) : extractErrorMessage(e, fallback);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={{ padding: 20, gap: 20 }}
        keyboardShouldPersistTaps="handled">
        <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 20 }}>
          {CONSENT_INTRO}
        </Text>

        {/* Date of birth card */}
        <View
          style={{
            borderRadius: 12,
            borderWidth: 1,
            borderColor: Colors.border,
            padding: 14,
            gap: 8,
            backgroundColor: Colors.surface,
          }}>
          <Text
            style={{
              fontFamily: Fonts.sansSemiBold,
              fontSize: 14,
              color: Colors.textPrimary,
            }}>
            Date of birth
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Open date-of-birth picker"
            onPress={() => setShowPicker(true)}
            style={({ pressed }) => ({
              borderRadius: 10,
              borderWidth: dob ? 1 : 2,
              borderColor: dob ? Colors.border : Colors.primary,
              backgroundColor: pressed
                ? Colors.surfaceMuted
                : dob
                  ? Colors.sidebarBg
                  : Colors.surface,
            })}>
            {/* Inner row View — NativeWind drops flexDirection on Pressable's style function */}
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                padding: 14,
              }}>
              <Calendar
                size={18}
                color={dob ? Colors.textSecondary : Colors.primary}
                style={{ marginRight: 10 }}
              />
              <Text
                style={{
                  flex: 1,
                  color: dob ? Colors.textPrimary : Colors.primary,
                  fontFamily: dob ? Fonts.sans : Fonts.sansSemiBold,
                  fontSize: 15,
                }}>
                {dob ? formatDateInput(dob) : 'Tap to select date of birth'}
              </Text>
              <ChevronDown size={16} color={dob ? Colors.textMuted : Colors.primary} />
            </View>
          </Pressable>

          {showPicker && (
            <View style={{ alignItems: 'center', marginTop: 4 }}>
              <DateTimePicker
                value={dob ?? initialPickerDate}
                mode="date"
                display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                maximumDate={maxDate}
                onChange={onPickerChange}
              />
              {Platform.OS === 'ios' && (
                <View style={{ alignSelf: 'flex-end' }}>
                  <Button
                    label="Done"
                    variant="secondary"
                    size="sm"
                    onPress={() => setShowPicker(false)}
                  />
                </View>
              )}
            </View>
          )}

          <Text
            style={{
              fontSize: 12,
              color: Colors.textMuted,
              lineHeight: 17,
            }}>
            WondrLink is for adults (18+). We use your date of birth only to verify age — the raw
            date is not stored.
          </Text>
          {dob && !isAdult && (
            <Text style={{ color: Colors.danger, fontSize: 13 }}>
              You must be at least 18 years old to create an account.
            </Text>
          )}
        </View>

        {/* State card */}
        <View
          style={{
            borderRadius: 12,
            borderWidth: 1,
            borderColor: Colors.border,
            padding: 14,
            gap: 8,
            backgroundColor: Colors.surface,
          }}>
          <Select
            label="State of residence"
            value={state}
            onChange={(v) => setState(v as StateChoice)}
            options={stateOptions}
            placeholder="Select your state…"
          />
        </View>

        {/* Consents card */}
        <View
          style={{
            borderRadius: 12,
            borderWidth: 1,
            borderColor: Colors.border,
            padding: 14,
            gap: 6,
            backgroundColor: Colors.surface,
          }}>
          <Text
            style={{
              fontFamily: Fonts.sansSemiBold,
              fontSize: 14,
              color: Colors.textPrimary,
              marginBottom: 2,
            }}>
            Please confirm each consent independently
          </Text>

          <Checkbox
            label={CONSENT_LABELS.consent_collection}
            checked={collection}
            onChange={setCollection}
          />
          <Checkbox
            label={CONSENT_LABELS.consent_sharing}
            checked={sharing}
            onChange={setSharing}
          />
          <Checkbox
            label={CONSENT_LABELS.consent_terms}
            checked={terms}
            onChange={setTerms}
            description="Includes the Consumer Health Data Privacy Notice."
          />
        </View>

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
