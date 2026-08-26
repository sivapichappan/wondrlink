/**
 * Who are you here for? (mockup screen 03) — the ONE onboarding question
 * that survived the redesign, because it re-voices the entire app.
 *
 * It used to hand the answer to a "just four things" form; that form is
 * gone (change 5) and the answer is saved right here. Everything else,
 * starting with what to call this person, is asked in the conversation.
 * Tapping advances; there is no continue button and no wrong answer.
 */

import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { HeartHandshake, User } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { IconCircle } from '@/components/ui/IconCircle';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { saveAccountPerspective } from '@/lib/api/account';
import { APP_NAME } from '@shared/branding';


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
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const choose = async (perspective: 'self' | 'caregiver') => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await saveAccountPerspective(perspective);
      // The gate reads this to know the question is answered.
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
      router.replace('/');
    } catch {
      setError('Could not save that just now. Please try again.');
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ flexGrow: 1, padding: Spacing.xl, justifyContent: 'center', gap: Spacing.lg }}
        showsVerticalScrollIndicator={false}>
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
            {`${APP_NAME} helps you make sense of cancer care, in plain words.`}
          </Text>
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
          onPress={() => choose('self')}
        />
        <Choice
          title="A loved one"
          subtitle="I am caring for someone"
          icon={<HeartHandshake size={20} color={Colors.primaryPressed} />}
          onPress={() => choose('caregiver')}
        />

        {error ? (
          <Text style={{ fontSize: FontSize.sm, color: Colors.warning, textAlign: 'center' }}>
            {error}
          </Text>
        ) : null}

        <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted, textAlign: 'center', marginTop: Spacing.md }}>
          You can change this later in Settings.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
