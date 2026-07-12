import { useQuery } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { ChevronRight, ExternalLink } from 'lucide-react-native';
import { ActivityIndicator, Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { ApiError } from '@/lib/api/client';
import { fetchClinicalTrials } from '@/lib/api/tools';

export default function ClinicalTrialsScreen() {
  const trials = useQuery({
    queryKey: ['clinical_trials'],
    queryFn: () => fetchClinicalTrials(10),
    retry: 0,
  });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Clinical trials', headerBackTitle: 'Tools' }} />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
        {trials.isLoading && (
          <View style={{ alignItems: 'center', paddingVertical: 40 }}>
            <ActivityIndicator color={Colors.primary} />
            <Text style={{ color: Colors.textMuted, marginTop: 10, fontSize: 12 }}>
              Searching ClinicalTrials.gov…
            </Text>
          </View>
        )}

        {trials.isError && (
          <ErrorBlock err={trials.error} onBack={() => router.back()} />
        )}

        {trials.data && trials.data.trials.length === 0 && !trials.isError && (
          <Text style={{ color: Colors.textSecondary, fontSize: 13 }}>
            No trials matched your profile right now. Try refining your profile (stage, biomarkers,
            ZIP code) in the Care tab.
          </Text>
        )}

        {trials.data && trials.data.trials.length > 0 && (
          <>
            <Text style={{ color: Colors.textMuted, fontSize: 12 }}>
              {trials.data.total_found ?? trials.data.trials.length} matching trials. Tap to open on
              ClinicalTrials.gov.
            </Text>
            {trials.data.trials.map((t) => {
              const url = t.url || `https://clinicaltrials.gov/study/${t.nct_id}`;
              return (
                <Pressable
                  key={t.nct_id}
                  onPress={() => Linking.openURL(url).catch(() => {})}
                  accessibilityRole="link"
                  accessibilityLabel={`${t.title}. ${t.status ?? ''}. Opens on ClinicalTrials.gov`}
                  style={({ pressed }) => ({
                    padding: 16,
                    borderRadius: Radius.lg,
                    borderWidth: 1,
                    borderColor: Colors.border,
                    backgroundColor: pressed ? Colors.surfaceMuted : Colors.surface,
                    gap: 8,
                    shadowColor: Colors.textPrimary,
                    shadowOpacity: 0.06,
                    shadowRadius: 8,
                    shadowOffset: { width: 0, height: 2 },
                    elevation: 2,
                  })}>
                  <View
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                    }}>
                    <Text
                      style={{ color: Colors.textMuted, fontSize: 11, fontFamily: Fonts.sansMedium }}>
                      {t.nct_id}
                      {t.phase ? ` · ${t.phase}` : ''}
                    </Text>
                    {t.status ? <StatusPill status={t.status} /> : null}
                  </View>
                  <Text
                    style={{
                      color: Colors.textPrimary,
                      fontFamily: Fonts.sansSemiBold,
                      fontSize: 15,
                      lineHeight: 21,
                    }}>
                    {t.title}
                  </Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 }}>
                    <ExternalLink size={13} color={Colors.primary} />
                    <Text style={{ color: Colors.primary, fontSize: 12, fontFamily: Fonts.sansMedium }}>
                      View on ClinicalTrials.gov
                    </Text>
                    <ChevronRight size={16} color={Colors.primary} style={{ marginLeft: 'auto' }} />
                  </View>
                </Pressable>
              );
            })}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function StatusPill({ status }: { status: string }) {
  // Recruiting / enrolling = actionable (teal); everything else = muted.
  const recruiting = /^(recruiting|enrolling)/i.test(status);
  return (
    <View
      style={{
        flexShrink: 0,
        paddingHorizontal: 8,
        paddingVertical: 3,
        borderRadius: Radius.pill,
        backgroundColor: recruiting ? Colors.primarySoft : Colors.sidebarBg,
      }}>
      <Text
        numberOfLines={1}
        style={{
          color: recruiting ? Colors.primary : Colors.textMuted,
          fontSize: 11,
          fontFamily: Fonts.sansSemiBold,
        }}>
        {status}
      </Text>
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
