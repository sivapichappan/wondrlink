/**
 * The basics (Sage doc screens 2a/2b) — just four things; everything else is
 * learned in conversation. Caregiver branch adds their name + relationship.
 * Location is free text (city or postal code), stored as a display string;
 * a US ZIP also feeds trial matching directly.
 */

import { useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { saveAccountBasics } from '@/lib/api/account';
import { ApiError, extractErrorMessage } from '@/lib/api/client';

const RELATIONSHIPS = ['Mom', 'Dad', 'Spouse', 'Child', 'Friend', 'Other'] as const;
const GENDERS = ['Female', 'Male', 'Other'] as const;

function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label}>
      <View
        style={{
          paddingHorizontal: 14,
          paddingVertical: 8,
          borderRadius: Radius.pill,
          borderWidth: on ? 2 : 1,
          borderColor: on ? Colors.primary : Colors.border,
          backgroundColor: on ? Colors.primarySoft : Colors.surface,
        }}>
        <Text
          style={{
            fontSize: FontSize.base,
            color: on ? Colors.primaryPressed : Colors.textSecondary,
            fontFamily: on ? Fonts.sansSemiBold : Fonts.sans,
          }}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

export default function Basics() {
  const params = useLocalSearchParams<{ perspective?: string }>();
  const perspective = params.perspective === 'caregiver' ? 'caregiver' : 'self';
  const caregiver = perspective === 'caregiver';

  const [yourName, setYourName] = useState('');
  const [theirName, setTheirName] = useState('');
  const [relationship, setRelationship] = useState<string | null>(null);
  const [birthYear, setBirthYear] = useState('');
  const [gender, setGender] = useState<string | null>(null);
  const [locationText, setLocationText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  const patientLabel = caregiver ? (theirName.trim() || 'them') : 'you';

  const onSubmit = async () => {
    setError(null);
    if (!yourName.trim()) {
      setError('Please tell us your name.');
      return;
    }
    if (caregiver && !theirName.trim()) {
      setError('Please tell us their name.');
      return;
    }
    setBusy(true);
    try {
      await saveAccountBasics({
        perspective,
        account_holder_name: yourName.trim(),
        patient_name: caregiver ? theirName.trim() : yourName.trim(),
        relationship: caregiver ? (relationship ?? undefined) : undefined,
        birth_year: /^\d{4}$/.test(birthYear.trim()) ? Number(birthYear.trim()) : undefined,
        gender: (GENDERS as readonly string[]).includes(gender ?? '')
          ? (gender as 'Female' | 'Male' | 'Other')
          : undefined,
        location: locationText.trim() ? { display: locationText.trim() } : undefined,
      });
      // Root layout re-reads the gate and routes into the app.
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      await qc.invalidateQueries({ queryKey: ['profile'] });
    } catch (e) {
      const fallback = 'Could not save. Please try again.';
      setError(e instanceof ApiError ? extractErrorMessage(e.body, fallback) : fallback);
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={{ padding: Spacing.xl, gap: Spacing.lg, flexGrow: 1 }}
          keyboardShouldPersistTaps="handled">
          <View style={{ gap: 6 }}>
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: 26, color: Colors.textPrimary }}>
              {caregiver ? 'About you and them' : 'Just four things'}
            </Text>
            <Text style={{ fontSize: FontSize.md, lineHeight: 21, color: Colors.textSecondary }}>
              Everything else, Sage learns as you chat.
            </Text>
          </View>

          <TextField label="Your name" value={yourName} onChangeText={setYourName} autoFocus />

          {caregiver && (
            <>
              <TextField label="Their name" value={theirName} onChangeText={setTheirName} />
              <View style={{ gap: 8 }}>
                <Text style={{ color: Colors.textSecondary, fontSize: FontSize.xs, fontFamily: Fonts.sansMedium }}>
                  They are your
                </Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                  {RELATIONSHIPS.map((r) => (
                    <Chip key={r} label={r} on={relationship === r} onPress={() => setRelationship(r)} />
                  ))}
                </View>
              </View>
            </>
          )}

          <TextField
            label={caregiver ? `${patientLabel}'s year of birth` : 'Year of birth'}
            value={birthYear}
            onChangeText={setBirthYear}
            placeholder="1962"
            keyboardType="number-pad"
            maxLength={4}
          />

          <View style={{ gap: 8 }}>
            <Text style={{ color: Colors.textSecondary, fontSize: FontSize.xs, fontFamily: Fonts.sansMedium }}>
              {caregiver ? `${patientLabel}'s gender` : 'Gender'}
            </Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {GENDERS.map((g) => (
                <Chip key={g} label={g} on={gender === g} onPress={() => setGender(g)} />
              ))}
            </View>
          </View>

          <View style={{ gap: 4 }}>
            <TextField
              label={caregiver ? `Where ${patientLabel} lives` : 'Where you live'}
              value={locationText}
              onChangeText={setLocationText}
              placeholder="City or ZIP code"
            />
            <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted }}>
              Helps Sage find trials and care nearby. You can skip this for now.
            </Text>
          </View>

          {error ? (
            <View style={{ backgroundColor: Colors.warningBg, borderRadius: Radius.md, padding: Spacing.md }}>
              <Text style={{ color: Colors.textPrimary, fontSize: FontSize.base }}>{error}</Text>
            </View>
          ) : null}

          <View style={{ marginTop: 'auto', paddingBottom: Spacing.lg }}>
            <Button
              label={busy ? 'Saving…' : caregiver ? 'Continue' : 'Start chatting'}
              size="lg"
              fullWidth
              disabled={busy}
              onPress={onSubmit}
            />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
