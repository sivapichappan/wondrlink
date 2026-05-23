/**
 * Consent Management screen — MHMDA Task 4 parity.
 *
 * Two toggleable consents (collection + sharing); the third (terms) is
 * display-only because re-toggling terms acceptance requires re-reading
 * the docs. Withdrawing collection or sharing logs an immutable row in
 * consent_withdrawals on the server and immediately disables /api/chat
 * (HTTP 403 + code:CONSENT_WITHDRAWN). The chat screen's banner picks
 * this up via fetchConsentStatus().
 *
 * Mirrors public/index.html's Consent Management section shipped in
 * web commit d44dd96.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { useCallback } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { fetchConsentStatus, withdrawConsent } from '@/lib/api/consent';
import type { ConsentStatusResponse } from '@shared/types';

type ToggleKey = 'consent_collection' | 'consent_sharing';

const TOGGLES: Array<{
  key: ToggleKey;
  title: string;
  help: string;
  withdrawWarning: string;
}> = [
  {
    key: 'consent_collection',
    title: '1. Health data collection',
    help: 'Off = WondrLink stops processing new health data. Existing data is retained for your records.',
    withdrawWarning:
      'This will stop WondrLink from processing new data. Existing data is retained. Continue?',
  },
  {
    key: 'consent_sharing',
    title: '2. AI provider processing',
    help: 'Off = chat is disabled. WondrLink cannot generate responses without sharing de-identified queries with its AI providers.',
    withdrawWarning:
      'Withdrawing this consent will disable chat completely. You can re-enable it any time. Continue?',
  },
];

function formatTimestamp(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString();
}

export default function ConsentManagement() {
  const qc = useQueryClient();
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['consent-status'],
    queryFn: fetchConsentStatus,
  });

  const onToggle = useCallback(
    async (key: ToggleKey, currentlyGranted: boolean) => {
      const action = currentlyGranted ? 'withdraw' : 'restore';
      if (action === 'withdraw') {
        const def = TOGGLES.find((t) => t.key === key);
        const ok = await new Promise<boolean>((resolve) => {
          Alert.alert('Withdraw consent', def?.withdrawWarning ?? 'Continue?', [
            { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
            { text: 'Withdraw', style: 'destructive', onPress: () => resolve(true) },
          ]);
        });
        if (!ok) return;
      }
      try {
        await withdrawConsent({ consent_key: key, action });
        await refetch();
        // Invalidate the chat-related queries so the chat-disabled banner
        // re-renders on next tab switch.
        await qc.invalidateQueries({ queryKey: ['consent-status'] });
      } catch (e) {
        const msg =
          e instanceof ApiError ? e.body?.error ?? 'Failed to update consent.' : 'Network error.';
        Alert.alert('Could not update', msg);
      }
    },
    [refetch, qc],
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Consent Management' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
        <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
          Toggle any consent off to stop the related processing. Toggling off does{' '}
          <Text style={{ fontFamily: Fonts.sansSemiBold }}>not</Text> delete your data —
          use Delete Account for that.
        </Text>

        {isLoading && (
          <Text style={{ color: Colors.textMuted, fontSize: 13 }}>Loading current state…</Text>
        )}

        {!isLoading &&
          data &&
          TOGGLES.map((def) => {
            const row = data[def.key];
            const granted = row?.granted !== false;
            const changedAt = row?.changed_at;
            return (
              <View
                key={def.key}
                style={{
                  borderWidth: 1,
                  borderColor: Colors.border,
                  borderRadius: 12,
                  padding: 14,
                  gap: 8,
                }}>
                <View
                  style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text
                    style={{
                      fontFamily: Fonts.sansSemiBold,
                      fontSize: 14,
                      color: Colors.textPrimary,
                      flex: 1,
                    }}>
                    {def.title}
                  </Text>
                  <Button
                    label={granted ? 'Withdraw' : 'Re-enable'}
                    size="sm"
                    variant={granted ? 'ghost' : 'primary'}
                    onPress={() => onToggle(def.key, granted)}
                  />
                </View>
                <Text style={{ color: Colors.textSecondary, fontSize: 12, lineHeight: 17 }}>
                  {def.help}
                </Text>
                <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>
                  Status:{' '}
                  <Text
                    style={{
                      color: granted ? Colors.primary : Colors.danger,
                      fontFamily: Fonts.sansSemiBold,
                    }}>
                    {granted ? 'On' : 'Off (withdrawn)'}
                  </Text>
                </Text>
                {changedAt && (
                  <Text style={{ color: Colors.textMuted, fontSize: 11 }}>
                    Last changed {formatTimestamp(changedAt)}
                  </Text>
                )}
              </View>
            );
          })}

        <View
          style={{
            borderWidth: 1,
            borderColor: Colors.border,
            borderRadius: 12,
            padding: 14,
            gap: 6,
            backgroundColor: Colors.sidebarBg,
          }}>
          <Text
            style={{ fontFamily: Fonts.sansSemiBold, fontSize: 13, color: Colors.textPrimary }}>
            3. Terms of Use + Privacy Policy
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 12, lineHeight: 17 }}>
            Display-only. Re-reading and re-accepting happens automatically when policies are
            updated.
          </Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 4 }}>
            <Pressable onPress={() => router.push('/settings/privacy')}>
              <Text style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 12 }}>
                Privacy Policy →
              </Text>
            </Pressable>
            <Pressable onPress={() => router.push('/settings/terms')}>
              <Text style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 12 }}>
                Terms of Use →
              </Text>
            </Pressable>
            <Pressable onPress={() => router.push('/settings/health-notice')}>
              <Text style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 12 }}>
                Consumer Health Data Notice →
              </Text>
            </Pressable>
          </View>
        </View>

        {data?.chat_disabled && (
          <View
            style={{
              padding: 12,
              borderRadius: 10,
              backgroundColor: Colors.warningBg,
              borderWidth: 1,
              borderColor: Colors.warning,
            }}>
            <Text style={{ color: Colors.textPrimary, fontSize: 13, lineHeight: 18 }}>
              <Text style={{ fontFamily: Fonts.sansSemiBold }}>Chat is currently disabled.</Text>{' '}
              Re-enable a consent above to use chat again.
            </Text>
          </View>
        )}

        {isFetching && !isLoading && (
          <Text style={{ color: Colors.textMuted, fontSize: 11, textAlign: 'center' }}>
            Refreshing…
          </Text>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
