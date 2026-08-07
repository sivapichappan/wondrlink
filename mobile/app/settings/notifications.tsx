/**
 * "Tell me when an answer is ready."
 *
 * A permanent, NON-PROMPTING home for the thing that is otherwise offered once,
 * in the chat, the first time leaving mid-question actually pays off. Two people
 * need this screen: whoever said no thanks, and whoever never left the app at
 * the wrong moment and so was never asked.
 *
 * It never fires the system prompt on its own. iOS allows one per install and
 * after a denial the only route back is Settings, so a screen that asked just by
 * being opened could burn it on someone who was only having a look around.
 */

import { Stack } from 'expo-router';
import { BellRing } from 'lucide-react-native';
import { useCallback, useEffect, useState } from 'react';
import { Linking, Pressable, ScrollView, Text, View } from 'react-native';

import { HeaderBack } from '@/components/common/HeaderBack';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { pushPermissionStatus, registerForPush, type PushPermission } from '@/lib/push';
import { APP_NAME } from '@shared/branding';

export default function NotificationSettingsScreen() {
  const [status, setStatus] = useState<PushPermission | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    pushPermissionStatus().then(setStatus).catch(() => setStatus('unavailable'));
  }, []);

  useEffect(refresh, [refresh]);

  const turnOn = async () => {
    setBusy(true);
    await registerForPush();
    refresh();
    setBusy(false);
  };

  return (
    <>
      <Stack.Screen options={{ title: 'Notifications', headerLeft: () => <HeaderBack /> }} />
      <ScrollView contentContainerStyle={{ padding: Spacing.xl, gap: Spacing.lg }}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm }}>
          <BellRing size={18} color={Colors.primary} style={{ marginTop: 2 }} />
          <Text
            style={{
              flex: 1,
              color: Colors.textPrimary,
              fontSize: FontSize.lg,
              lineHeight: 22,
              fontFamily: Fonts.sansSemiBold,
            }}>
            Tell me when an answer is ready
          </Text>
        </View>

        <Text
          style={{
            color: Colors.textSecondary,
            fontSize: FontSize.base,
            lineHeight: 20,
            fontFamily: Fonts.sans,
          }}>
          {`Some questions take ${APP_NAME} a little while to work through. You can close the app while it does, and the answer will be waiting when you come back. Turn this on and you will get a nudge the moment it lands.`}
        </Text>

        <Text
          style={{
            color: Colors.textMuted,
            fontSize: FontSize.sm,
            lineHeight: 18,
            fontFamily: Fonts.sans,
          }}>
          The notification only says an answer is ready. It never shows what you asked or anything
          about your health, because it appears on your lock screen.
        </Text>

        {status === 'granted' && (
          <Text style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.base }}>
            Notifications are on for this device.
          </Text>
        )}

        {status === 'denied' && (
          <View style={{ gap: Spacing.sm }}>
            <Text style={{ color: Colors.textSecondary, fontSize: FontSize.base, lineHeight: 20 }}>
              Notifications are turned off for this app. iOS only lets us ask once, so this one has
              to be changed in your phone settings.
            </Text>
            <Pressable
              onPress={() => Linking.openSettings().catch(() => {})}
              accessibilityRole="button"
              accessibilityLabel="Open iPhone settings"
              style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1, alignSelf: 'flex-start' })}>
              <View
                style={{
                  paddingVertical: Spacing.sm,
                  paddingHorizontal: Spacing.lg,
                  borderRadius: Radius.pill,
                  backgroundColor: Colors.primary,
                }}>
                <Text style={{ color: Colors.surface, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.base }}>
                  Open phone settings
                </Text>
              </View>
            </Pressable>
          </View>
        )}

        {status === 'unavailable' && (
          <Text style={{ color: Colors.textMuted, fontSize: FontSize.base, lineHeight: 20 }}>
            This device cannot receive notifications.
          </Text>
        )}

        {status === null && (
          <Pressable
            onPress={turnOn}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Turn on notifications"
            style={({ pressed }) => ({ opacity: pressed || busy ? 0.7 : 1, alignSelf: 'flex-start' })}>
            <View
              style={{
                paddingVertical: Spacing.sm,
                paddingHorizontal: Spacing.lg,
                borderRadius: Radius.pill,
                backgroundColor: Colors.primary,
              }}>
              <Text style={{ color: Colors.surface, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.base }}>
                Turn on notifications
              </Text>
            </View>
          </Pressable>
        )}
      </ScrollView>
    </>
  );
}
