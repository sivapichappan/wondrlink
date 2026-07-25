/**
 * Who are you here for? (Sage doc screen 2) — the one branch that shapes the
 * voice of every screen after it. Own uncluttered screen, one tap, no wrong
 * answers. The choice rides to the basics screen and is saved there.
 */

import { router } from 'expo-router';
import { Activity, HeartHandshake, MessageCircle, Microscope, NotebookPen, User } from 'lucide-react-native';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { IconCircle } from '@/components/ui/IconCircle';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { APP_NAME } from '@shared/branding';

function Tip({ Icon, text }: { Icon: typeof Activity; text: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm }}>
      <Icon size={16} color={Colors.primary} style={{ marginTop: 2 }} />
      <Text style={{ flex: 1, fontSize: FontSize.sm, lineHeight: 19, color: Colors.textSecondary }}>
        {text}
      </Text>
    </View>
  );
}

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
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ flexGrow: 1, padding: Spacing.xl, justifyContent: 'center', gap: Spacing.lg }}
        showsVerticalScrollIndicator={false}>
        {/* What-is-this intro + how to use it well: the first screen after
            consent is where a new person learns what the app does and the
            habits that make it useful (check-ins, visit recaps, details). */}
        <View style={{ gap: 6 }}>
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
            {`${APP_NAME} helps you make sense of cancer care, in plain words. Here is how to get the most from it:`}
          </Text>
        </View>

        <View
          style={{
            gap: Spacing.sm,
            backgroundColor: Colors.surfaceMuted,
            borderRadius: Radius.lg,
            padding: Spacing.lg,
            marginBottom: Spacing.md,
          }}>
          <Tip Icon={MessageCircle} text="Just talk. Ask anything, anytime, like you would ask a nurse." />
          <Tip Icon={Activity} text="Do the wellness check-in when it appears. It tracks how you feel from week to week, so changes get noticed." />
          <Tip Icon={NotebookPen} text="After appointments, use Sum up a doctor visit to turn notes into plain words and next steps." />
          <Tip Icon={Microscope} text={`Share details when you're ready. The more ${APP_NAME} knows, the better it can match clinical trials to you.`} />
        </View>
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
            {`This shapes how ${APP_NAME} talks with you. You can not get it wrong.`}
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
      </ScrollView>
    </SafeAreaView>
  );
}
