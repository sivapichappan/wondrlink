/**
 * Applying to review medical content (SPEC §5.2, adapted).
 *
 * §5.2 says "No self-registration. No public signup." That intent is kept
 * exactly: submitting this creates a row with status 'requested', which passes
 * NO review route. An admin activates the account, and until then this person
 * gets the same refusal a stranger does.
 *
 * The credential fields are not paperwork. An attestation snapshots the
 * signer's capacity at the moment they sign, so what the admin verified has to
 * be stored beside the decision rather than living in an email somewhere.
 *
 * MD or DO is required and checked before submit. Only a physician may hold an
 * attesting role; the database enforces it too, and failing here says why
 * instead of surfacing a constraint name.
 */

import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { TextField } from '@/components/ui/TextField';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { ApiError, extractErrorMessage } from '@/lib/api/client';
import { applyAsReviewer } from '@/lib/api/review';
import { supabase } from '@/lib/supabase';

const CREDENTIALS = ['MD', 'DO'] as const;

function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label}>
      <View
        style={{
          paddingHorizontal: 18,
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

export default function ReviewerApply() {
  const [fullName, setFullName] = useState('');
  const [credential, setCredential] = useState<'MD' | 'DO' | null>(null);
  const [npi, setNpi] = useState('');
  const [licenseState, setLicenseState] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [institution, setInstitution] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  const onSubmit = async () => {
    setError(null);
    if (!fullName.trim()) {
      setError('Please enter your full name.');
      return;
    }
    if (!credential) {
      setError('Please choose MD or DO. Only a physician can sign off on content.');
      return;
    }
    setBusy(true);
    try {
      const { data } = await supabase.auth.getUser();
      const email = data.user?.email;
      if (!email) {
        setError('We could not read your email. Please sign out and back in.');
        return;
      }
      await applyAsReviewer({
        full_name: fullName.trim(),
        credential,
        email,
        npi: npi.trim() || undefined,
        license_state: licenseState.trim() || undefined,
        specialty: specialty.trim() || undefined,
        institution: institution.trim() || undefined,
      });
      // The root gate re-reads the status and lands on the waiting screen.
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      router.replace('/(onboarding)/reviewer-pending' as never);
    } catch (e) {
      const fallback = 'Could not send your request. Please try again.';
      setError(e instanceof ApiError ? extractErrorMessage(e.body, fallback) : fallback);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen keyboardAvoiding keyboardShouldPersistTaps gap={Spacing.lg}>
      <View style={{ gap: 6 }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: 26, color: Colors.textPrimary }}>
          Request reviewer access
        </Text>
        <Text style={{ fontSize: FontSize.md, lineHeight: 21, color: Colors.textSecondary }}>
          Reviewers read proposed connections between treatments and side effects, check them
          against the source, and approve the wording patients will see.
        </Text>
      </View>

      <TextField
        label="Full name"
        value={fullName}
        onChangeText={setFullName}
        placeholder="Dr Jane Smith"
        autoFocus
      />

      <View style={{ gap: 8 }}>
        <Text
          style={{
            color: Colors.textSecondary,
            fontSize: FontSize.xs,
            fontFamily: Fonts.sansMedium,
          }}>
          Credential
        </Text>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {CREDENTIALS.map((c) => (
            <Chip key={c} label={c} on={credential === c} onPress={() => setCredential(c)} />
          ))}
        </View>
        <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted }}>
          Only a physician can sign off on what patients read.
        </Text>
      </View>

      <TextField
        label="NPI number"
        value={npi}
        onChangeText={setNpi}
        placeholder="Optional"
        keyboardType="number-pad"
        maxLength={10}
      />
      <TextField
        label="License state"
        value={licenseState}
        onChangeText={setLicenseState}
        placeholder="Optional, e.g. NJ"
        autoCapitalize="characters"
        maxLength={2}
      />
      <TextField
        label="Specialty"
        value={specialty}
        onChangeText={setSpecialty}
        placeholder="Optional, e.g. medical oncology"
      />
      <TextField
        label="Hospital or practice"
        value={institution}
        onChangeText={setInstitution}
        placeholder="Optional"
      />

      {error ? <Text style={{ color: Colors.danger, fontSize: FontSize.sm }}>{error}</Text> : null}

      <Button label="Send request" onPress={onSubmit} loading={busy} disabled={busy} />

      <Text style={{ fontSize: FontSize.xs, lineHeight: 17, color: Colors.textMuted }}>
        Someone on our team checks every request by hand. You will not be able to review or
        approve anything until they do.
      </Text>
    </Screen>
  );
}
