import { useQuery } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { CalendarClock } from 'lucide-react-native';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { fetchSurveillance } from '@/lib/api/tools';

export default function SurveillanceScreen() {
  const q = useQuery({
    queryKey: ['surveillance'],
    queryFn: fetchSurveillance,
  });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Surveillance', headerBackTitle: 'Tools' }} />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
        {q.isLoading && <ActivityIndicator color={Colors.primary} />}

        {q.data && !q.data.schedule && (
          <View
            style={{
              padding: 14,
              borderRadius: Radius.lg,
              backgroundColor: Colors.sidebarBg,
            }}>
            <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
              Profile incomplete
            </Text>
            <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 4 }}>
              {q.data.message ||
                'We need your stage and surgery date to build a surveillance schedule.'}
            </Text>
          </View>
        )}

        {q.data?.schedule && q.data.schedule.length > 0 && (
          <>
            <Text style={{ color: Colors.textMuted, fontSize: 12, lineHeight: 18 }}>
              Personalized timeline based on your stage and surgery date. Times are approximate —
              your oncologist may adjust.
            </Text>
            {q.data.schedule.map((m, i) => (
              <View
                key={i}
                style={{
                  flexDirection: 'row',
                  gap: 12,
                  padding: 12,
                  borderRadius: Radius.md,
                  borderWidth: 1,
                  borderColor: Colors.border,
                  backgroundColor: Colors.surface,
                }}>
                <View
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 18,
                    backgroundColor: Colors.sidebarBg,
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                  <CalendarClock size={18} color={Colors.primary} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text
                    style={{
                      color: Colors.textPrimary,
                      fontFamily: Fonts.sansSemiBold,
                      fontSize: 14,
                    }}>
                    {m.test}
                  </Text>
                  <Text style={{ color: Colors.textSecondary, fontSize: 12, marginTop: 2 }}>
                    {m.when}
                    {m.due_date ? ` · due ${m.due_date}` : ''}
                  </Text>
                  {m.rationale && (
                    <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 4 }}>
                      {m.rationale}
                    </Text>
                  )}
                </View>
              </View>
            ))}
          </>
        )}

        <Button label="Back to tools" variant="ghost" fullWidth onPress={() => router.back()} />
      </ScrollView>
    </SafeAreaView>
  );
}
