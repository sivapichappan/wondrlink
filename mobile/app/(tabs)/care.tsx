import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { User } from 'lucide-react-native';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { CareSnapshot } from '@/components/care/CareSnapshot';
import { HeroCard } from '@/components/care/HeroCard';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useCareSnapshot, useHero, useProfile } from '@/hooks/useCare';

export default function CareScreen() {
  const hero = useHero();
  const snap = useCareSnapshot();
  const profile = useProfile();
  const qc = useQueryClient();

  const askSuggestion = (q: string) => {
    router.push({ pathname: '/(tabs)/', params: { q } });
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
          Care
        </Text>

        {hero.data?.has_profile ? (
          <HeroCard hero={hero.data} onAskSuggestion={askSuggestion} />
        ) : (
          <ProfilePromptCard />
        )}

        <CareSnapshot snapshot={snap.data} />

        <Pressable
          onPress={() => router.push('/profile')}
          style={({ pressed }) => ({
            flexDirection: 'row',
            alignItems: 'center',
            gap: 10,
            padding: 14,
            borderRadius: Radius.lg,
            backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
            borderWidth: 1,
            borderColor: Colors.border,
          })}>
          <User size={18} color={Colors.primary} />
          <View style={{ flex: 1 }}>
            <Text
              style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
              {profile.data?.profile ? 'View your profile' : 'Set up your profile'}
            </Text>
            <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
              {profile.data?.profile
                ? 'See what WondrChat knows about you'
                : 'Personalize responses with your stage and treatments'}
            </Text>
          </View>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
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
