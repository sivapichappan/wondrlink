import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { Activity, ChevronRight, Tag, User } from 'lucide-react-native';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { CareSnapshot } from '@/components/care/CareSnapshot';
import { HeroCard } from '@/components/care/HeroCard';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useCareSnapshot, useHero, useProfile } from '@/hooks/useCare';

const WELLNESS_CHECKS: {
  key: 'PHQ9' | 'GAD7' | 'PSS10' | 'ISI' | 'SYMPTOM' | 'PREMM5';
  label: string;
}[] = [
  { key: 'SYMPTOM', label: 'Symptom check-in' },
  { key: 'PHQ9', label: 'Depression (PHQ-9)' },
  { key: 'GAD7', label: 'Anxiety (GAD-7)' },
  { key: 'PSS10', label: 'Stress (PSS-10)' },
  { key: 'ISI', label: 'Sleep (ISI)' },
];

export default function CareScreen() {
  const hero = useHero();
  const snap = useCareSnapshot();
  const profile = useProfile();
  const ack = useAcknowledgement();
  const qc = useQueryClient();

  const askSuggestion = (q: string) => {
    // Interim (Phase 1b): Home ('/') consumes ?q= and auto-sends.
    // Phase 2 repoints this to the /chat thread route.
    router.push({ pathname: '/', params: { q } });
  };

  const cancerDisplay =
    hero.data?.cancer_display ?? ack.data?.cancer_display ?? null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }}>
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
            Care
          </Text>
          <CancerFocusChip
            label={cancerDisplay ?? 'Pick cancer'}
            onPress={() => router.push('/profile/cancer-switcher')}
          />
        </View>

        {hero.data?.has_profile ? (
          <HeroCard hero={hero.data} onAskSuggestion={askSuggestion} />
        ) : (
          <ProfilePromptCard />
        )}

        <CareSnapshot snapshot={snap.data} />

        <View
          style={{
            borderRadius: Radius.lg,
            borderWidth: 1,
            borderColor: Colors.border,
            padding: 14,
            gap: 10,
            backgroundColor: Colors.surfaceMuted,
          }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Activity size={16} color={Colors.primary} />
            <Text
              style={{ fontFamily: Fonts.sansSemiBold, fontSize: 14, color: Colors.textPrimary }}>
              Wellness check-in
            </Text>
          </View>
          <Text style={{ color: Colors.textMuted, fontSize: 12 }}>
            Quick, standardized screenings. Results save to your snapshot.
          </Text>
          <View style={{ gap: 6 }}>
            {WELLNESS_CHECKS.map((w) => (
              <Pressable
                key={w.key}
                onPress={() =>
                  router.push({ pathname: '/tools/screening', params: { instrument: w.key } })
                }
                accessibilityRole="button"
                accessibilityLabel={`Start ${w.label} check-in`}
                style={({ pressed }) => ({
                  borderRadius: Radius.sm,
                  backgroundColor: pressed ? Colors.surfaceMuted : Colors.sidebarBg,
                })}>
                <View
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    paddingVertical: 12,
                    paddingHorizontal: 12,
                  }}>
                  <Text style={{ flex: 1, color: Colors.textPrimary, fontSize: 14 }}>
                    {w.label}
                  </Text>
                  <ChevronRight size={16} color={Colors.primary} />
                </View>
              </Pressable>
            ))}
          </View>
        </View>

        <Pressable
          onPress={() => router.push({ pathname: '/profile' })}
          accessibilityRole="button"
          accessibilityLabel={profile.data?.profile ? 'View your profile' : 'Set up your profile'}
          style={({ pressed }) => ({
            borderRadius: Radius.lg,
            backgroundColor: pressed ? Colors.primarySoft : Colors.surfaceMuted,
            borderWidth: 1,
            borderColor: Colors.border,
          })}>
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              padding: 14,
            }}>
            <User size={18} color={Colors.primary} style={{ marginRight: 10 }} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text
                style={{
                  color: Colors.textPrimary,
                  fontFamily: Fonts.sansSemiBold,
                  fontSize: 14,
                }}>
                {profile.data?.profile ? 'View your profile' : 'Set up your profile'}
              </Text>
              <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
                {profile.data?.profile
                  ? 'See what WondrChat knows about you'
                  : 'Personalize responses with your stage and treatments'}
              </Text>
            </View>
            <ChevronRight size={18} color={Colors.primary} style={{ marginLeft: 8 }} />
          </View>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

function CancerFocusChip({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Cancer focus: ${label}. Tap to change.`}
      hitSlop={6}
      style={({ pressed }) => ({
        borderRadius: 999,
        borderWidth: 1,
        borderColor: pressed ? Colors.primary : Colors.border,
        backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
      })}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          paddingHorizontal: 10,
          paddingVertical: 6,
        }}>
        <Tag size={12} color={Colors.primary} style={{ marginRight: 4 }} />
        <Text
          numberOfLines={1}
          style={{
            color: Colors.primary,
            fontFamily: Fonts.sansMedium,
            fontSize: 12,
            maxWidth: 160,
          }}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

function ProfilePromptCard() {
  return (
    <View
      style={{
        backgroundColor: Colors.sidebarBg,
        borderRadius: Radius.lg,
        padding: 14,
      }}>
      <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 14, color: Colors.textPrimary }}>
        Add your profile for personalized answers
      </Text>
      <Text style={{ color: Colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 4 }}>
        Once you add your diagnosis and current treatments, WondrChat can tailor its responses to
        your situation.
      </Text>
    </View>
  );
}
