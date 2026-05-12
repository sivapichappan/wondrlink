import { useQueryClient } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import { Alert, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useProfile } from '@/hooks/useCare';
import { clearProfile } from '@/lib/api/care';

export default function ProfileScreen() {
  const profile = useProfile();
  const qc = useQueryClient();

  const reset = () => {
    Alert.alert(
      'Reset your profile?',
      'This removes the personalized profile WondrChat uses to tailor answers. Your chat history is unaffected.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: async () => {
            await clearProfile();
            qc.invalidateQueries({ queryKey: ['profile'] });
            qc.invalidateQueries({ queryKey: ['hero'] });
          },
        },
      ],
    );
  };

  const p = profile.data?.profile;
  const patient = (p?.patient ?? {}) as { firstName?: string; name?: string; age?: number; sex?: string };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Profile', headerBackTitle: 'Care' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
        {!p ? (
          <View style={{ gap: 8 }}>
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: 20, color: Colors.textPrimary }}>
              No profile yet
            </Text>
            <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
              For v1 you can set up a profile on the WondrChat web app at wondrlink.foundation.
              The mobile app will pick it up automatically here.
            </Text>
            <Button label="Back to Care" variant="secondary" fullWidth onPress={() => router.back()} />
          </View>
        ) : (
          <>
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
              {patient.firstName || patient.name || 'Your profile'}
            </Text>
            {profile.data?.patient_summary ? (
              <View
                style={{
                  backgroundColor: Colors.sidebarBg,
                  borderRadius: Radius.md,
                  padding: 14,
                }}>
                <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 20 }}>
                  {profile.data.patient_summary}
                </Text>
              </View>
            ) : null}
            <Stat label="Age" value={patient.age != null ? String(patient.age) : '—'} />
            <Stat label="Sex" value={patient.sex || '—'} />
            <Stat
              label="Treatments on record"
              value={Array.isArray(p.treatments) ? String(p.treatments.length) : '—'}
            />
            <Stat
              label="Biomarkers on record"
              value={Array.isArray(p.biomarkers) ? String(p.biomarkers.length) : '—'}
            />
            <View style={{ height: 8 }} />
            <Button label="Reset profile" variant="danger" fullWidth onPress={reset} />
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View
      style={{
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingVertical: 10,
        borderBottomWidth: 1,
        borderBottomColor: Colors.border,
      }}>
      <Text style={{ color: Colors.textSecondary, fontSize: 13 }}>{label}</Text>
      <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
        {value}
      </Text>
    </View>
  );
}
