/**
 * Limit Use of Sensitive Personal Information — CCPA / CPRA affordance.
 *
 * Parity with the web modal shipped in commit 49bcff7. Operationally a
 * no-op because WondrLink doesn't sell or share SPI for advertising;
 * the screen explains the no-op honestly and records the user's
 * preference timestamp for auditability.
 *
 * The "Do Not Sell or Share My Personal Information" Settings entry
 * also routes here (one backend, two visible surfaces).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { useCallback } from 'react';
import { Alert, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts } from '@/constants/theme';
import { confirmLimitSpi, getLimitSpi } from '@/lib/api/account';
import { ApiError } from '@/lib/api/client';

function formatTimestamp(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString();
}

export default function LimitSpi() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['limit-spi'],
    queryFn: getLimitSpi,
  });

  const mut = useMutation({
    mutationFn: confirmLimitSpi,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['limit-spi'] }),
    onError: (err) => {
      const msg =
        err instanceof ApiError ? err.body?.error ?? 'Failed to save.' : 'Network error.';
      Alert.alert('Could not save preference', msg);
    },
  });

  const onConfirm = useCallback(() => mut.mutate(), [mut]);

  const limited = data?.limited === true;
  const confirmedAt = data?.confirmed_at ?? null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Limit Use of Sensitive PI' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
        <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
          Under the California Consumer Privacy Act (CCPA / CPRA), residents have the right to
          limit how their sensitive personal information is used. This page describes how WondrLink
          already limits use, and confirms your preference for our records.
        </Text>

        <Section title="What we treat as Sensitive Personal Information (SPI)">
          <Bullet>Your cancer diagnosis, stage, and treatments</Bullet>
          <Bullet>Biomarkers, genetic test results, and family history fields</Bullet>
          <Bullet>Mental-health screening results (PHQ-9, GAD-7, PSS-10, ISI)</Bullet>
          <Bullet>Symptom logs and PRO-CTCAE entries</Bullet>
          <Bullet>Any other clinical detail you share in chat or in your profile</Bullet>
        </Section>

        <Section title="How we use your SPI today">
          <Bullet>
            <Strong>To provide the WondrLink service.</Strong> Personalize education, surface
            relevant clinical-trial matches, render survivorship rubrics, and ground LLM responses
            in the guidelines that apply to your situation.
          </Bullet>
          <Bullet>
            <Strong>To process safely.</Strong> Direct identifiers (name, DOB, address, phone,
            email, MRN, insurance ID, account numbers, ZIP code) are stripped before any query is
            sent to our LLM providers.
          </Bullet>
        </Section>

        <Section title="How we DO NOT use your SPI">
          <Bullet><Strong>We do not sell</Strong> your sensitive personal information.</Bullet>
          <Bullet>
            <Strong>We do not share</Strong> it for cross-context behavioral advertising or any
            third-party advertising purpose.
          </Bullet>
          <Bullet>
            <Strong>We do not use</Strong> it for inferences unrelated to providing the WondrLink
            service.
          </Bullet>
          <Bullet>
            <Strong>We do not use</Strong> it for profiling that produces legal or similarly
            significant effects.
          </Bullet>
        </Section>

        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
          Because we already limit use as described above, tapping "Confirm my preference" below
          produces no behavioral change in how we process your data — but it records your
          preference so we can demonstrate it on request.
        </Text>

        <View
          style={{
            backgroundColor: Colors.sidebarBg,
            padding: 12,
            borderRadius: 10,
          }}>
          {isLoading ? (
            <Text style={{ color: Colors.textMuted, fontSize: 13 }}>Loading current preference…</Text>
          ) : limited ? (
            <Text style={{ color: Colors.textPrimary, fontSize: 13, lineHeight: 19 }}>
              <Text style={{ fontFamily: Fonts.sansSemiBold }}>Preference confirmed.</Text>{' '}
              Recorded on {formatTimestamp(confirmedAt)}.
            </Text>
          ) : (
            <Text style={{ color: Colors.textPrimary, fontSize: 13 }}>
              You have not confirmed a preference yet.
            </Text>
          )}
        </View>

        <Button
          label={limited ? 'Re-confirm my preference' : 'Confirm my preference'}
          fullWidth
          size="lg"
          loading={mut.isPending}
          onPress={onConfirm}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 14, color: Colors.textPrimary }}>
        {title}
      </Text>
      <View style={{ gap: 4 }}>{children}</View>
    </View>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      <Text style={{ color: Colors.textMuted, fontSize: 13 }}>•</Text>
      <Text style={{ flex: 1, color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
        {children}
      </Text>
    </View>
  );
}

function Strong({ children }: { children: React.ReactNode }) {
  return (
    <Text style={{ fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>{children}</Text>
  );
}
