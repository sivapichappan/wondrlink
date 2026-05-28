import { useQuery } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { Activity, Bed, Brain, HeartPulse, Smile } from 'lucide-react-native';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Sparkline } from '@/components/care/Sparkline';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { fetchScreeningHistory, type ScreeningHistoryPoint } from '@/lib/api/tools';

interface InstrumentMeta {
  key: string;
  title: string;
  Icon: typeof Activity;
  max: number;
  color: string;
}

const INSTRUMENTS: InstrumentMeta[] = [
  { key: 'SYMPTOM', title: 'Symptoms', Icon: Activity, max: 40, color: Colors.accent },
  { key: 'PHQ9', title: 'Depression (PHQ-9)', Icon: Smile, max: 27, color: Colors.primary },
  { key: 'GAD7', title: 'Anxiety (GAD-7)', Icon: Brain, max: 21, color: Colors.primary },
  { key: 'PSS10', title: 'Stress (PSS-10)', Icon: HeartPulse, max: 40, color: Colors.primary },
  { key: 'ISI', title: 'Sleep (ISI)', Icon: Bed, max: 28, color: Colors.primary },
];

export default function TrendsScreen() {
  const history = useQuery({
    queryKey: ['screening_history'],
    queryFn: fetchScreeningHistory,
    staleTime: 30_000,
  });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Trends' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 14, paddingBottom: 40 }}>
        <View style={{ gap: 4 }}>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
            Your wellness trends
          </Text>
          <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
            How your check-ins are tracking over time. Share these with your care team if anything
            looks off.
          </Text>
        </View>

        {history.isLoading ? (
          <View style={{ padding: 40, alignItems: 'center' }}>
            <ActivityIndicator color={Colors.primary} />
          </View>
        ) : history.isError ? (
          <Text style={{ color: Colors.danger, fontSize: 13 }}>
            Could not load history. Pull to retry.
          </Text>
        ) : (
          INSTRUMENTS.map((inst) => (
            <TrendCard
              key={inst.key}
              meta={inst}
              points={history.data?.history?.[inst.key] ?? []}
            />
          ))
        )}

        <Button
          label="Take a check-in"
          variant="secondary"
          fullWidth
          onPress={() => router.push('/tools/screening')}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function TrendCard({ meta, points }: { meta: InstrumentMeta; points: ScreeningHistoryPoint[] }) {
  const recent = points.slice(-8);
  const latest = recent.length > 0 ? recent[recent.length - 1] : null;
  const values = recent.map((p) => p.total_score);

  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        padding: 14,
        gap: 10,
        backgroundColor: Colors.surface,
      }}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <View
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            backgroundColor: Colors.sidebarBg,
            alignItems: 'center',
            justifyContent: 'center',
            marginRight: 10,
          }}>
          <meta.Icon size={18} color={meta.color} />
        </View>
        <View style={{ flex: 1 }}>
          <Text
            style={{
              fontFamily: Fonts.sansSemiBold,
              fontSize: 15,
              color: Colors.textPrimary,
            }}>
            {meta.title}
          </Text>
          <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
            {points.length === 0
              ? 'No entries yet'
              : `${points.length} entr${points.length === 1 ? 'y' : 'ies'} · last on ${formatDate(latest!.created_at)}`}
          </Text>
        </View>
        {latest && (
          <View style={{ alignItems: 'flex-end' }}>
            <Text
              style={{
                fontFamily: Fonts.serifBold,
                fontSize: 22,
                color: Colors.textPrimary,
              }}>
              {latest.total_score}
            </Text>
            {latest.severity_label ? (
              <Text style={{ color: Colors.textMuted, fontSize: 11 }}>
                {latest.severity_label}
              </Text>
            ) : null}
          </View>
        )}
      </View>

      {values.length >= 2 ? (
        <View style={{ alignItems: 'center' }}>
          <Sparkline values={values} max={meta.max} color={meta.color} width={280} height={60} />
        </View>
      ) : values.length === 1 ? (
        <Text style={{ color: Colors.textMuted, fontSize: 12, fontStyle: 'italic' }}>
          One entry — take another to see a trend.
        </Text>
      ) : null}
    </View>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}
