/**
 * "Want a nudge next time?" — offered the first time recovery actually helps.
 *
 * WHERE THIS IS ASKED IS THE WHOLE DESIGN. iOS gives one system prompt per
 * install, and after a denial the only way back is Settings. Asking at launch
 * spends it before the person knows what would be sent. Asking while they are
 * watching a typing indicator spends it on someone anxious and distracted.
 *
 * So it is offered at the one moment the value has already been PROVEN rather
 * than predicted: they left the app mid-question, came back, and the answer was
 * waiting. The card describes a thing that just happened to them.
 *
 * Self-limiting by construction, since only people the feature actually helps
 * ever reach it. Shown once either way: taking a "no" as a permanent answer is
 * the difference between an offer and nagging. Settings has a permanent row for
 * anyone who changes their mind.
 */

import { BellRing } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { registerForPush } from '@/lib/push';

interface Props {
  onDismiss: () => void;
}

export function NotifyOffer({ onDismiss }: Props) {
  const [busy, setBusy] = useState(false);

  const enable = async () => {
    setBusy(true);
    // registerForPush never throws and returns 'unavailable' on a simulator.
    // Either way the offer is done: it has been made once.
    await registerForPush();
    onDismiss();
  };

  return (
    <View
      style={{
        marginHorizontal: Spacing.md,
        marginBottom: Spacing.sm,
        padding: Spacing.md,
        borderRadius: Radius.md,
        borderWidth: 1,
        borderColor: Colors.border,
        backgroundColor: Colors.sidebarBg,
        gap: Spacing.sm,
      }}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm }}>
        <BellRing size={16} color={Colors.primary} style={{ marginTop: 2 }} />
        <Text
          style={{
            flex: 1,
            color: Colors.textPrimary,
            fontSize: FontSize.base,
            lineHeight: 19,
            fontFamily: Fonts.sans,
          }}>
          You left while that answer was still coming, and it was waiting when you got back.
          Want a nudge next time?
        </Text>
      </View>
      <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
        <Pressable
          onPress={enable}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="Turn on notifications for finished answers"
          style={({ pressed }) => ({ opacity: pressed || busy ? 0.7 : 1 })}>
          <View
            style={{
              paddingVertical: Spacing.sm,
              paddingHorizontal: Spacing.md,
              borderRadius: Radius.pill,
              backgroundColor: Colors.primary,
            }}>
            <Text
              style={{
                color: Colors.surface,
                fontFamily: Fonts.sansSemiBold,
                fontSize: FontSize.sm,
              }}>
              Yes, notify me
            </Text>
          </View>
        </Pressable>
        <Pressable
          onPress={onDismiss}
          accessibilityRole="button"
          accessibilityLabel="No thanks"
          style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}>
          <View
            style={{
              paddingVertical: Spacing.sm,
              paddingHorizontal: Spacing.md,
              borderRadius: Radius.pill,
              borderWidth: 1,
              borderColor: Colors.border,
              backgroundColor: Colors.surface,
            }}>
            <Text
              style={{
                color: Colors.textSecondary,
                fontFamily: Fonts.sansSemiBold,
                fontSize: FontSize.sm,
              }}>
              No thanks
            </Text>
          </View>
        </Pressable>
      </View>
    </View>
  );
}
