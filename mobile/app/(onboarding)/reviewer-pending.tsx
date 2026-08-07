/**
 * Waiting on an admin.
 *
 * This screen IS the wave-1 notification. Push needs a native module and a real
 * build, so what a pending applicant gets today is a place that tells them
 * exactly where their request stands, refreshed every time they open the app.
 * That is deliberately not a placeholder: "nothing happened, is it broken?" is
 * the actual failure mode of an approval queue, and a screen that answers it
 * removes most of the reason to notify at all.
 *
 * There is nowhere else for this account to go. A reviewer may not hold a
 * patient profile — the database enforces it in both directions — so sending
 * them into patient onboarding would end in a profile that permanently blocks
 * the account from ever being approved.
 */

import { useQueryClient } from '@tanstack/react-query';
import { Bell, CircleCheck, Clock } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { RefreshControl, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { useReviewerSession } from '@/hooks/useReviewerSession';
import { logout } from '@/lib/api/auth';
import { pushPermissionStatus, registerForPush, type PushPermission } from '@/lib/push';
import { APP_NAME } from '@shared/branding';

function Step({ done, title, body }: { done: boolean; title: string; body: string }) {
  return (
    <View style={{ flexDirection: 'row', gap: Spacing.md, alignItems: 'flex-start' }}>
      {done ? (
        <CircleCheck size={20} color={Colors.primary} style={{ marginTop: 1 }} />
      ) : (
        <Clock size={20} color={Colors.textMuted} style={{ marginTop: 1 }} />
      )}
      <View style={{ flex: 1, gap: 2 }}>
        <Text
          style={{
            fontSize: FontSize.base,
            fontFamily: Fonts.sansSemiBold,
            color: done ? Colors.textPrimary : Colors.textSecondary,
          }}>
          {title}
        </Text>
        <Text style={{ fontSize: FontSize.sm, lineHeight: 19, color: Colors.textMuted }}>
          {body}
        </Text>
      </View>
    </View>
  );
}

export default function ReviewerPending() {
  const { status } = useReviewerSession();
  const qc = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [push, setPush] = useState<PushPermission | null>(null);
  const [asking, setAsking] = useState(false);

  // Read the existing answer WITHOUT asking. iOS gives one system prompt per
  // install, so it must be spent on a deliberate tap, not on arriving here.
  useEffect(() => {
    pushPermissionStatus().then(setPush);
  }, []);

  const turnOnNotifications = async () => {
    setAsking(true);
    try {
      setPush(await registerForPush());
    } finally {
      setAsking(false);
    }
  };

  const signOut = async () => {
    // logout() drops the push token itself, so every sign-out path gets it.
    await logout();
    await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
  };

  // Pull to refresh, and a button for the same thing. Someone waiting on a
  // decision will check; the gesture is not discoverable enough to be the only
  // way to do it.
  const recheck = async () => {
    setRefreshing(true);
    try {
      await qc.invalidateQueries({ queryKey: ['acknowledgement'] });
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <Screen
      gap={Spacing.lg}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={recheck} tintColor={Colors.primary} />
      }>
      <View style={{ gap: 6, marginTop: Spacing.xl }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: 26, color: Colors.textPrimary }}>
          Your request is in
        </Text>
        <Text style={{ fontSize: FontSize.md, lineHeight: 21, color: Colors.textSecondary }}>
          {status === 'invited'
            ? `Someone on the ${APP_NAME} team set up your account. It becomes active once they finish.`
            : `Someone on the ${APP_NAME} team reads every request by hand. We will let you know as soon as it is done.`}
        </Text>
      </View>

      <View
        style={{
          gap: Spacing.lg,
          backgroundColor: Colors.surfaceMuted,
          borderRadius: Radius.lg,
          padding: Spacing.lg,
        }}>
        <Step
          done
          title="You asked for access"
          body="Your name, credential and practice went with it."
        />
        <Step
          done={false}
          title="We check your credentials"
          body="Usually a day or two. Nothing to do in the meantime."
        />
        <Step
          done={false}
          title="You get the full app"
          body="Chat, tools, and a review queue in the menu."
        />
      </View>

      {/* The one moment the ask makes obvious sense: the question on their mind
          right now is "how will I know?". Nothing here is shown until the
          device answers, so a simulator or a phone that already said yes never
          sees a dead button. */}
      {push === 'unasked' ? (
        <View
          style={{
            flexDirection: 'row',
            gap: Spacing.md,
            alignItems: 'flex-start',
            backgroundColor: Colors.surfaceMuted,
            borderRadius: Radius.lg,
            padding: Spacing.lg,
          }}>
          <Bell size={20} color={Colors.primary} style={{ marginTop: 1 }} />
          <View style={{ flex: 1, gap: Spacing.sm }}>
            <Text style={{ fontSize: FontSize.sm, lineHeight: 19, color: Colors.textSecondary }}>
              Want a notification the moment you are approved? Otherwise just open the app to
              check.
            </Text>
            <Button
              label="Notify me"
              variant="secondary"
              size="sm"
              onPress={turnOnNotifications}
              loading={asking}
              disabled={asking}
            />
          </View>
        </View>
      ) : push === 'granted' ? (
        <View style={{ flexDirection: 'row', gap: Spacing.sm, alignItems: 'center' }}>
          <Bell size={15} color={Colors.textMuted} />
          <Text style={{ flex: 1, fontSize: FontSize.sm, color: Colors.textMuted }}>
            We will send you a notification as soon as you are approved.
          </Text>
        </View>
      ) : push === 'denied' ? (
        // The button cannot help here: iOS shows its prompt once, and after a
        // refusal only the phone's own settings can change it. Saying so beats
        // a button that silently does nothing.
        <View style={{ flexDirection: 'row', gap: Spacing.sm, alignItems: 'center' }}>
          <Bell size={15} color={Colors.textMuted} />
          <Text style={{ flex: 1, fontSize: FontSize.sm, color: Colors.textMuted }}>
            Notifications are off for this app. Turn them on in your phone settings if you would
            like to be told, or just open the app to check.
          </Text>
        </View>
      ) : null}

      <Button label="Check again" variant="secondary" onPress={recheck} loading={refreshing} />

      <Text style={{ fontSize: FontSize.xs, lineHeight: 17, color: Colors.textMuted }}>
        Wrong account? Sign out and start again with a different email. One account cannot be both
        a patient account and a reviewer account.
      </Text>
      <Button label="Sign out" variant="ghost" onPress={() => signOut()} />
    </Screen>
  );
}
