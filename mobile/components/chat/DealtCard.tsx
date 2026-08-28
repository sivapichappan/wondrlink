/**
 * DealtCard — the card Sage deals into the conversation (mockup screen 05).
 *
 * The nine-tool grid is gone. Everything that used to be a tool now arrives
 * here, at the moment it is relevant, inside the conversation: a scan
 * suggestion when there are papers to read, the trials ask when trials are
 * within reach, pre-visit questions before a visit.
 *
 * The sage accent border is what distinguishes a dealt card from one of
 * Sage's plain messages; the title is interface (sans), because the card is
 * a thing to act on rather than Sage speaking.
 *
 * Engagement is instrumented here rather than at each call site, so a new
 * card cannot ship unmeasured: mounting logs `shown`, the primary action
 * logs `acted`, the escape hatch logs `dismissed`.
 */

import { useEffect, useRef } from 'react';
import { Text, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { PressableScale } from '@/components/ui/PressableScale';
import { cardEnter, cardExit } from '@/constants/motion';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import * as haptics from '@/lib/haptics';
import { logCardEvent, type CardKind } from '@/lib/api/cards';

interface Props {
  kind: CardKind;
  icon?: React.ReactNode;
  title: string;
  body?: string;
  /** Primary action. Omit for a card that only offers chips. */
  actionLabel?: string;
  onAction?: () => void;
  /** Rule 6: every ask carries a way out. */
  dismissLabel?: string;
  onDismiss?: () => void;
  /** Chips rendered under the body (e.g. the cancer picker). */
  children?: React.ReactNode;
}

export function DealtCard({
  kind,
  icon,
  title,
  body,
  actionLabel,
  onAction,
  dismissLabel = 'Not now',
  onDismiss,
  children,
}: Props) {
  const logged = useRef(false);
  useEffect(() => {
    if (logged.current) return;
    logged.current = true;
    void logCardEvent(kind, 'shown');
  }, [kind]);

  return (
    // It is called a dealt card, so it should arrive like one: a short rise
    // and settle rather than blinking into existence beside the answer it
    // belongs to. Exits the way it entered, so dismissing reads as the
    // reverse of arriving rather than as the card vanishing.
    <Animated.View
      entering={cardEnter()}
      exiting={cardExit()}
      style={{
        backgroundColor: Colors.surface,
        borderWidth: 1,
        borderColor: Colors.accentBorder,
        borderRadius: Radius.lg,
        padding: Spacing.lg,
        gap: Spacing.sm,
      }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }}>
        {icon}
        <Text
          style={{
            flex: 1,
            fontFamily: Fonts.sansSemiBold,
            fontSize: FontSize.lg,
            color: Colors.textPrimary,
          }}>
          {title}
        </Text>
      </View>

      {!!body && (
        <Text style={{ color: Colors.textSecondary, fontSize: FontSize.md, lineHeight: 21 }}>
          {body}
        </Text>
      )}

      {children}

      {(onAction || onDismiss) && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginTop: Spacing.xs }}>
          {onAction && !!actionLabel && (
            <PressableScale
              onPress={() => {
                void logCardEvent(kind, 'acted');
                onAction();
              }}
              accessibilityRole="button"
              accessibilityLabel={actionLabel}>
              {/* Visuals on a static inner View — NativeWind strips them from
                  Pressable style functions. */}
              <View
                style={{
                  backgroundColor: Colors.primary,
                  paddingHorizontal: Spacing.lg,
                  paddingVertical: 10,
                  borderRadius: Radius.md,
                }}>
                <Text
                  style={{
                    color: Colors.surface,
                    fontFamily: Fonts.sansSemiBold,
                    fontSize: FontSize.md,
                  }}>
                  {actionLabel}
                </Text>
              </View>
            </PressableScale>
          )}
          {onDismiss && (
            <PressableScale
              onPress={() => {
                void logCardEvent(kind, 'dismissed');
                // Something snapping home. One per action, and never on a
                // crisis surface — this is a card being put away.
                haptics.snap();
                onDismiss();
              }}
              accessibilityRole="button"
              accessibilityLabel={dismissLabel}>
              <View style={{ paddingHorizontal: Spacing.md, paddingVertical: 10 }}>
                <Text
                  style={{
                    color: Colors.primaryPressed,
                    fontFamily: Fonts.sansSemiBold,
                    fontSize: FontSize.md,
                  }}>
                  {dismissLabel}
                </Text>
              </View>
            </PressableScale>
          )}
        </View>
      )}
    </Animated.View>
  );
}

/** The quiet, borderless chip the mockups use for escape hatches. */
export function CardChip({
  label,
  onPress,
  quiet,
  disabled,
}: {
  label: string;
  onPress: () => void;
  quiet?: boolean;
  disabled?: boolean;
}) {
  return (
    // The single most-tapped element in the new chat flow: every check-in
    // answer and every cancer-picker choice goes through it. It previously
    // had no press state at all, only a disabled dim, so answering a
    // check-in felt like tapping a picture of a button.
    <PressableScale
      onPress={() => {
        // A chip is a value ticking past a step, which is the lightest
        // haptic there is. Fired here, at the causal moment, rather than
        // after the send resolves.
        haptics.selection();
        onPress();
      }}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      // The visual is under 44pt tall; grow the target, not the chip.
      hitSlop={8}>
      <View
        style={{
          paddingHorizontal: 16,
          paddingVertical: 9,
          borderRadius: Radius.pill,
          borderWidth: quiet ? 0 : 1.5,
          borderColor: Colors.accentBorder,
          backgroundColor: quiet ? 'transparent' : Colors.surface,
          opacity: disabled ? 0.5 : 1,
        }}>
        <Text
          style={{
            fontSize: FontSize.md,
            fontFamily: Fonts.sansMedium,
            color: quiet ? Colors.textSecondary : Colors.primaryPressed,
          }}>
          {label}
        </Text>
      </View>
    </PressableScale>
  );
}
