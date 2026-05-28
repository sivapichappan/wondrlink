import { useQueryClient } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { AlertTriangle } from 'lucide-react-native';
import { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { TextField } from '@/components/ui/TextField';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { deleteAccount } from '@/lib/api/account';
import { logout } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';

const CONFIRM_PHRASE = 'DELETE';

export default function DeleteAccount() {
  const qc = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const [phrase, setPhrase] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canDelete = confirmed && phrase.trim().toUpperCase() === CONFIRM_PHRASE;

  const onDelete = async () => {
    if (!canDelete) return;
    setSubmitting(true);
    setError(null);
    try {
      await deleteAccount();
      await logout();
      qc.clear();
      // Root layout will route to (auth)/welcome after session clears.
    } catch (e) {
      setError(
        e instanceof ApiError ? e.body?.error ?? 'Could not delete account.' : 'Could not delete account.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Delete account' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
        <View style={{ alignItems: 'center', marginVertical: 12 }}>
          <View
            style={{
              width: 56,
              height: 56,
              borderRadius: 28,
              backgroundColor: Colors.emergencyBg,
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <AlertTriangle size={28} color={Colors.danger} />
          </View>
        </View>

        <Text
          style={{
            fontFamily: Fonts.serifBold,
            fontSize: 22,
            color: Colors.textPrimary,
            textAlign: 'center',
          }}>
          Permanently delete your account
        </Text>

        <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
          This removes your account and all associated data from our primary database within 30
          days. Sub-processor logs may persist beyond this window per their retention policies.
        </Text>

        <View
          style={{
            padding: 12,
            backgroundColor: Colors.sidebarBg,
            borderRadius: Radius.md,
            gap: 4,
          }}>
          <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 13, color: Colors.textPrimary }}>
            What gets deleted
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 12, lineHeight: 18 }}>
            • Your account email and login{'\n'}
            • Your patient profile (diagnosis, treatments, biomarkers){'\n'}
            • Your chat history{'\n'}
            • Your screening history (PHQ-9 etc.){'\n'}
            • Your visit recaps and pre-visit questions{'\n'}
            • Your insurance appeal drafts
          </Text>
        </View>

        <Checkbox
          label="I understand this is permanent and cannot be undone."
          checked={confirmed}
          onChange={setConfirmed}
        />

        <TextField
          label={`Type ${CONFIRM_PHRASE} to confirm`}
          autoCapitalize="characters"
          value={phrase}
          onChangeText={setPhrase}
        />

        {error && <Text style={{ color: Colors.danger, fontSize: 13 }}>{error}</Text>}

        <Button
          label="Delete my account permanently"
          variant="danger"
          fullWidth
          size="lg"
          loading={submitting}
          disabled={!canDelete}
          onPress={onDelete}
        />
        <Button label="Cancel" variant="ghost" fullWidth onPress={() => router.back()} />
      </ScrollView>
    </SafeAreaView>
  );
}
