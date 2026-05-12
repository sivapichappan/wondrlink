import { useQuery } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { ExternalLink } from 'lucide-react-native';
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
                  style={({ pressed }) => ({
                    padding: 14,
                    borderRadius: Radius.lg,
                    borderWidth: 1,
                    borderColor: Colors.border,
                    backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
                    gap: 6,
                  })}>
                  <Text style={{ color: Colors.textMuted, fontSize: 11, fontFamily: Fonts.sansMedium }}>
                    {t.nct_id} · {t.phase || 'Phase n/a'}
                  </Text>
                  <Text
                    style={{
                      color: Colors.textPrimary,
                      fontFamily: Fonts.sansSemiBold,
                      fontSize: 14,
                      lineHeight: 20,
                    }}>
                    {t.title}
                  </Text>
                  {t.status && (
                    <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>{t.status}</Text>
                  )}
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 }}>
                    <ExternalLink size={12} color={Colors.primary} />
                    <Text style={{ color: Colors.primary, fontSize: 12, fontFamily: Fonts.sansMedium }}>
                      View on ClinicalTrials.gov
                    </Text>
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
      <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
        Need a bit more information
      </Text>
      <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>{message}</Text>
      {missing.length > 0 && (
        <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>
          Missing: {missing.join(', ')}
        </Text>
      )}
      <Button label="Back to tools" variant="secondary" fullWidth onPress={onBack} />
    </View>
  );
}
