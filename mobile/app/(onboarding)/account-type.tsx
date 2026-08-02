/**
 * Which kind of account is this? The first screen after signing up.
 *
 * Two paths that must never cross: a patient account and a reviewer account are
 * mutually exclusive at the database, in both directions, and there is no undo
 * — finishing patient onboarding creates a profile that permanently blocks the
 * account from ever becoming a reviewer. So the fork happens here, before
 * anything is written, and before patient consent is asked for: the consent on
 * the next screen is a patient agreeing to have their health data processed,
 * which is not what a clinician reviewing content is agreeing to.
 *
 * Nearly everyone taps the first option. It is first, it is larger, and it is
 * the one that reads like a sentence about them.
 */

import { router } from 'expo-router';
import { HeartHandshake, Stethoscope } from 'lucide-react-native';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { IconCircle } from '@/components/ui/IconCircle';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { APP_NAME } from '@shared/branding';

function Choice({
  title,
  subtitle,
  icon,
  emphasis,
  onPress,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  emphasis?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={title}>
      {/* Visuals on a static inner View: NativeWind strips them from a
          Pressable's pressed-style function. */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: Spacing.md,
          borderWidth: emphasis ? 1.5 : 1,
          borderColor: emphasis ? Colors.primary : Colors.border,
          borderRadius: Radius.lg,
          padding: Spacing.lg,
          backgroundColor: Colors.surface,
        }}>
        <IconCircle size={44} bg={emphasis ? Colors.primarySoft : Colors.surfaceMuted}>
          {icon}
        </IconCircle>
        <View style={{ flex: 1 }}>
          <Text
            style={{
              fontSize: FontSize.lg,
              fontFamily: Fonts.sansSemiBold,
              color: Colors.textPrimary,
            }}>
            {title}
          </Text>
          <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted, marginTop: 2 }}>
            {subtitle}
          </Text>
        </View>
      </View>
    </Pressable>
  );
}

export default function AccountType() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{
          flexGrow: 1,
          padding: Spacing.xl,
          justifyContent: 'center',
          gap: Spacing.lg,
        }}
        showsVerticalScrollIndicator={false}>
        <View style={{ gap: 6, marginBottom: Spacing.md }}>
          <Text
            style={{
              fontFamily: Fonts.serifBold,
              fontSize: FontSize.h2,
              color: Colors.textPrimary,
              textAlign: 'center',
            }}>
            {`Welcome to ${APP_NAME}`}
          </Text>
          <Text
            style={{
              fontSize: FontSize.md,
              lineHeight: 21,
              color: Colors.textSecondary,
              textAlign: 'center',
            }}>
            What brings you here?
          </Text>
        </View>

        <Choice
          emphasis
          title="I am here about cancer care"
          subtitle="For myself or someone I care for"
          icon={<HeartHandshake size={20} color={Colors.primaryPressed} />}
          onPress={() => router.push('/(onboarding)/consent' as never)}
        />
        <Choice
          title="I am an oncologist"
          subtitle="I want to review medical content"
          icon={<Stethoscope size={20} color={Colors.textSecondary} />}
          onPress={() => router.push('/(onboarding)/reviewer-apply' as never)}
        />

        <Text
          style={{
            fontSize: FontSize.xs,
            lineHeight: 17,
            color: Colors.textMuted,
            textAlign: 'center',
            marginTop: Spacing.md,
          }}>
          One account cannot be both. Pick the one that fits, and reach us if you need the other
          later.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
