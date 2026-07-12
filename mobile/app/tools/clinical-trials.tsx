import { useQuery } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { TrialCard } from '@/components/trials/TrialCard';
import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useWatchlist } from '@/hooks/useWatchlist';
import { ApiError } from '@/lib/api/client';
import { fetchClinicalTrials } from '@/lib/api/tools';
import type { ChatClinicalTrial, TrialRadius } from '@shared/types';

const RADII: { value: TrialRadius; label: string; phrase: string }[] = [
  { value: 25, label: '25 mi', phrase: 'within 25 miles' },
  { value: 50, label: '50 mi', phrase: 'within 50 miles' },
  { value: 100, label: '100 mi', phrase: 'within 100 miles' },
  { value: 'nationwide', label: 'Nationwide', phrase: 'across the U.S.' },
];

const within = (t: ChatClinicalTrial, radius: TrialRadius) =>
  radius === 'nationwide' ||
  t.nearest_distance_miles == null ||
  t.nearest_distance_miles <= radius;

export default function ClinicalTrialsScreen() {
  const [radius, setRadius] = useState<TrialRadius>(100);
  const { isSaved, save, remove } = useWatchlist();

  // One fetch: the patient's top matches nationwide (with distances) + the
  // per-radius recruiting totals. The radius control filters this pool
  // client-side, so switching radius is instant with no refetch.
  const q = useQuery({
    queryKey: ['clinical_trials_pool'],
    queryFn: () => fetchClinicalTrials(12, 'nationwide', { counts: true }),
    retry: 0,
  });

  const pool = q.data?.trials ?? [];
  const counts = q.data?.radius_counts ?? null;
  const shown = pool.filter((t) => within(t, radius));
  const hidden =
    radius === 'nationwide'
      ? []
      : pool.filter((t) => t.nearest_distance_miles != null && t.nearest_distance_miles > radius);

  const radiusMeta = RADII.find((r) => r.value === radius)!;
  const count = counts?.[String(radius)] ?? shown.length;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surfaceMuted }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Clinical trials', headerBackTitle: 'Tools' }} />
      <ScrollView>
        {/* Header */}
        <View style={{ paddingHorizontal: 16, paddingTop: 22, gap: 3 }}>
          <Text style={{ fontFamily: Fonts.sansBold, fontSize: 18, color: Colors.textPrimary }}>
            Studies that match you
          </Text>
          <Text style={{ fontSize: 12, color: Colors.textMuted }}>
            Matched to your health profile · strongest first
          </Text>
        </View>

        {/* Filter block */}
        <View
          style={{
            paddingHorizontal: 16,
            paddingVertical: 14,
            borderBottomWidth: 1,
            borderBottomColor: Colors.border,
            gap: 10,
          }}>
          <Text style={{ fontSize: 12, fontFamily: Fonts.sansSemiBold, color: Colors.textSecondary }}>
            How far can you travel?
          </Text>
          <View
            accessibilityRole="radiogroup"
            style={{
              flexDirection: 'row',
              gap: 2,
              backgroundColor: Colors.sidebarBg,
              borderRadius: Radius.md,
              padding: 3,
            }}>
            {RADII.map((r) => {
              const active = radius === r.value;
              return (
                <Pressable
                  key={String(r.value)}
                  onPress={() => setRadius(r.value)}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                  style={{
                    flex: 1,
                    minHeight: 44,
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: Radius.sm,
                    borderWidth: 1,
                    borderColor: active ? Colors.border : 'transparent',
                    backgroundColor: active ? Colors.surface : 'transparent',
                    ...(active
                      ? {
                          shadowColor: Colors.textPrimary,
                          shadowOpacity: 0.1,
                          shadowRadius: 2,
                          shadowOffset: { width: 0, height: 1 },
                          elevation: 1,
                        }
                      : null),
                  }}>
                  <Text
                    style={{
                      fontSize: 12,
                      color: active ? Colors.primary : Colors.textMuted,
                      fontFamily: active ? Fonts.sansBold : Fonts.sansMedium,
                    }}>
                    {r.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          {q.data && !q.isError && (
            <View style={{ gap: 2 }}>
              <Text style={{ fontSize: 13, color: Colors.textPrimary }}>
                <Text style={{ fontFamily: Fonts.sansBold, color: Colors.primary }}>{count}</Text>{' '}
                recruiting trials {radiusMeta.phrase}
              </Text>
              {shown.length > 0 && (
                <Text style={{ fontSize: 12, color: Colors.textMuted }}>
                  Showing your top {shown.length} {shown.length === 1 ? 'match' : 'matches'} · sorted
                  by how well they fit you
                </Text>
              )}
            </View>
          )}
        </View>

        {/* Card list */}
        <View style={{ paddingHorizontal: 16, paddingTop: 16, paddingBottom: 26, gap: 14 }}>
          {q.isLoading && (
            <View style={{ alignItems: 'center', paddingVertical: 40 }}>
              <ActivityIndicator color={Colors.primary} />
              <Text style={{ color: Colors.textMuted, marginTop: 10, fontSize: 12 }}>
                Searching ClinicalTrials.gov…
              </Text>
            </View>
          )}

          {q.isError && <ErrorBlock err={q.error} onBack={() => router.back()} />}

          {q.data && !q.isError && pool.length === 0 && (
            <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
              No matching trials right now. Try refining your profile (stage, biomarkers, ZIP code)
              in the Care tab.
            </Text>
          )}

          {shown.map((t) => {
            const url = t.url || `https://clinicaltrials.gov/study/${t.nct_id}`;
            const isS = isSaved(t.nct_id);
            return (
              <TrialCard
                key={t.nct_id}
                trial={t}
                saved={isS}
                onToggleSave={() =>
                  isS ? remove(t.nct_id) : save({ nct_id: t.nct_id, title: t.title, phase: t.phase, url })
                }
              />
            );
          })}

          {hidden.length > 0 && <WidenCallout hidden={hidden} onWiden={setRadius} />}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function WidenCallout({
  hidden,
  onWiden,
}: {
  hidden: ChatClinicalTrial[];
  onWiden: (r: TrialRadius) => void;
}) {
  const ds = hidden
    .map((t) => t.nearest_distance_miles)
    .filter((d): d is number => d != null)
    .sort((a, b) => a - b);
  const parts = ds.map((d) => `${d} mi`);
  const joined =
    parts.length === 1
      ? parts[0]
      : parts.length === 2
        ? `${parts[0]} and ${parts[1]}`
        : `${parts.slice(0, 2).join(', ')}, and others`;
  const maxHidden = ds.length ? ds[ds.length - 1] : 0;
  const target: TrialRadius = maxHidden <= 50 ? 50 : maxHidden <= 100 ? 100 : 'nationwide';
  const targetLabel = target === 'nationwide' ? 'Search nationwide' : `Widen to ${target} miles`;
  const n = hidden.length;

  return (
    <View
      style={{
        borderWidth: 1.5,
        borderStyle: 'dashed',
        borderColor: Colors.primarySoft,
        backgroundColor: Colors.sidebarBg,
        borderRadius: Radius.lg,
        padding: 14,
        gap: 10,
        alignItems: 'flex-start',
      }}>
      <Text style={{ fontSize: 13, lineHeight: 19, color: Colors.textSecondary }}>
        {n} of your top {n === 1 ? 'matches is' : 'matches are'} outside this range ({joined} away).
      </Text>
      <Pressable
        onPress={() => onWiden(target)}
        accessibilityRole="button"
        style={({ pressed }) => ({
          minHeight: 44,
          paddingHorizontal: 16,
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: Radius.sm,
          borderWidth: 1.5,
          borderColor: Colors.primary,
          backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
        })}>
        <Text style={{ color: Colors.primary, fontSize: 13, fontFamily: Fonts.sansSemiBold }}>
          {targetLabel}
        </Text>
      </Pressable>
    </View>
  );
}

function ErrorBlock({ err, onBack }: { err: unknown; onBack: () => void }) {
  let message = 'Could not search trials right now.';
  let missing: string[] = [];
  if (err instanceof ApiError && err.body) {
    if (err.body.error) message = err.body.error;
    const mc = (err.body as { missing_critical?: string[] }).missing_critical;
    if (Array.isArray(mc)) missing = mc;
  }
  return (
    <View style={{ gap: 10 }}>
      <View
        style={{
          padding: 14,
          borderRadius: 12,
          backgroundColor: Colors.warningBg,
          borderWidth: 1,
          borderColor: Colors.warning,
          gap: 8,
        }}>
        <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
          Need a bit more information
        </Text>
        <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>{message}</Text>
        {missing.length > 0 && (
          <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>
            Missing: {missing.join(', ')}
          </Text>
        )}
      </View>
      <Button label="Back to tools" variant="secondary" fullWidth onPress={onBack} />
    </View>
  );
}
