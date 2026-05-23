/**
 * Region-blocked screen.
 *
 * Reached when /api/save_acknowledgement or /api/auth/register returns
 * HTTP 451 with code: REGION_BLOCKED — currently EU 27 + EEA + UK +
 * Switzerland (see lib/compliance.py BLOCKED_COUNTRIES and
 * docs/compliance/eu_geofence_decision.md for the rationale).
 *
 * Mirrors state-restricted.tsx in shape; copy is sourced from the
 * server message via the consent screen's catch block. We hardcode a
 * fallback message in case the screen is reached via direct navigation.
 */

import { useQueryClient } from '@tanstack/react-query';
import { Globe } from 'lucide-react-native';
import { Alert, Linking, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts } from '@/constants/theme';
import { logout } from '@/lib/api/auth';
import { apiFetch } from '@/lib/api/client';
import { ENDPOINTS } from '@shared/api-contracts';

const REGION_BLOCKED_TITLE = 'Not available in your region';
const REGION_BLOCKED_MESSAGE =
  "WondrLink is not currently available to residents of the EU, EEA, UK, or Switzerland. " +
  "We're working on compliance with the applicable regulations (GDPR, EU AI Act) and hope " +
  "to offer service in the future.";
const CONTACT_EMAIL = 'info@wondrlinkfoundation.org';

export default function RegionBlocked() {
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

  const contactUs = () => {
    Linking.openURL(`mailto:${CONTACT_EMAIL}?subject=WondrLink%20region%20availability`);
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
            <Globe size={28} color={Colors.warning} />
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
          {REGION_BLOCKED_TITLE}
        </Text>

        <Text
          style={{
            color: Colors.textSecondary,
            fontSize: 14,
            lineHeight: 21,
            textAlign: 'center',
          }}>
          {REGION_BLOCKED_MESSAGE}
        </Text>

        <Text
          style={{
            color: Colors.textMuted,
            fontSize: 12,
            lineHeight: 18,
            textAlign: 'center',
          }}>
          Contact us at {CONTACT_EMAIL} for updates. If you'd like to permanently remove the
          account you created, use the option below. Otherwise we'll sign you out.
        </Text>

        <View style={{ height: 8 }} />

        <Button label="Contact us" fullWidth size="lg" onPress={contactUs} />
        <Button label="Sign me out" variant="ghost" fullWidth onPress={signOut} />
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
