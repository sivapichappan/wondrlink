import { useQueryClient } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react-native';
import { Alert, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts } from '@/constants/theme';
import { logout } from '@/lib/api/auth';
import { apiFetch } from '@/lib/api/client';
import { ENDPOINTS } from '@shared/api-contracts';
import { STATE_BLOCKED_MESSAGE, STATE_BLOCKED_TITLE } from '@shared/disclaimers';

export default function StateRestricted() {
  const qc = useQueryClient();

  const signOut = async () => {
    await logout();
    await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
  };

  const deleteAccount = () => {
    Alert.alert(
      'Delete your account',
      'This permanently removes your WondrLink account and all associated data. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete account',
          style: 'destructive',
          onPress: async () => {
            try {
              await apiFetch(ENDPOINTS.deleteAccount, { method: 'DELETE' });
            } finally {
              await logout();
              await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
            }
          },
        },
      ],
    );
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <View style={{ flex: 1, padding: 24, gap: 18, justifyContent: 'center' }}>
        <View style={{ alignItems: 'center', marginBottom: 12 }}>
          <View
            style={{
              width: 56,
              height: 56,
              borderRadius: 28,
              backgroundColor: Colors.warningBg,
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <AlertTriangle size={28} color={Colors.warning} />
          </View>
        </View>

        <Text
          style={{
            fontFamily: Fonts.serifBold,
            fontSize: 22,
            color: Colors.textPrimary,
            textAlign: 'center',
            lineHeight: 28,
          }}>
          {STATE_BLOCKED_TITLE}
        </Text>

        <Text
          style={{
            color: Colors.textSecondary,
            fontSize: 14,
            lineHeight: 21,
            textAlign: 'center',
          }}>
          {STATE_BLOCKED_MESSAGE}
        </Text>

        <Text
          style={{
            color: Colors.textMuted,
            fontSize: 12,
            lineHeight: 18,
            textAlign: 'center',
          }}>
          If you'd like to permanently remove the account you created, use the option below.
          Otherwise we'll sign you out.
        </Text>

        <View style={{ height: 8 }} />

        <Button label="Sign me out" fullWidth size="lg" onPress={signOut} />
        <Button
          label="Delete my account"
          variant="ghost"
          fullWidth
          onPress={deleteAccount}
        />
      </View>
    </SafeAreaView>
  );
}
