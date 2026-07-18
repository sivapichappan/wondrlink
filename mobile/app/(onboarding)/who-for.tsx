/**
 * Who are you here for? (Sage doc screen 2) — the one branch that shapes the
 * voice of every screen after it. Own uncluttered screen, one tap, no wrong
 * answers. The choice rides to the basics screen and is saved there.
 */

import { router } from 'expo-router';
import { HeartHandshake, User } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { IconCircle } from '@/components/ui/IconCircle';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';

function Choice({
  title,
  subtitle,
  icon,
  onPress,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={title}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: Spacing.md,
          borderWidth: 1.5,
          borderColor: Colors.border,
          borderRadius: Radius.lg,
          padding: Spacing.lg,
          backgroundColor: Colors.surface,
        }}>
        <IconCircle size={44} bg={Colors.primarySoft}>
          {icon}
        </IconCircle>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: FontSize.lg, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
            {title}
          </Text>
          <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted, marginTop: 2 }}>{subtitle}</Text>
        </View>
      </View>
    </Pressable>
  );
}

export default function WhoFor() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }}>
      <View style={{ flex: 1, padding: Spacing.xl, justifyContent: 'center', gap: Spacing.lg }}>
        <View style={{ gap: 6, marginBottom: Spacing.md }}>
          <Text
            style={{
              fontFamily: Fonts.serifBold,
              fontSize: 26,
              color: Colors.textPrimary,
              textAlign: 'center',
            }}>
            Who are you here for?
          </Text>
          <Text
            style={{
              fontSize: FontSize.md,
              lineHeight: 21,
              color: Colors.textSecondary,
              textAlign: 'center',
            }}>
            This shapes how Sage talks with you. You can not get it wrong.
          </Text>
        </View>

        <Choice
          title="Myself"
          subtitle="I am the patient"
          icon={<User size={20} color={Colors.primaryPressed} />}
          onPress={() => router.push('/(onboarding)/basics?perspective=self' as never)}
        />
        <Choice
          title="A loved one"
          subtitle="I am caring for someone"
          icon={<HeartHandshake size={20} color={Colors.primaryPressed} />}
          onPress={() => router.push('/(onboarding)/basics?perspective=caregiver' as never)}
        />

        <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted, textAlign: 'center', marginTop: Spacing.md }}>
          You can change this later in Settings.
        </Text>
      </View>
    </SafeAreaView>
  );
}
