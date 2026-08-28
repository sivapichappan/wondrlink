/**
 * Skeleton — a loading state shaped like the thing it precedes.
 *
 * The app had none. Every async screen was a centred spinner, a bare
 * "Loading…", or nothing at all, and two primary surfaces rendered an empty
 * view and then popped their whole contents in at once. A spinner says the
 * app is busy; a skeleton says what is about to be there, which is the
 * difference between waiting and wondering whether something broke.
 *
 * Deliberately a slow, shallow opacity pulse rather than a travelling
 * shimmer. Shimmer is a small performance the user pays for on every load,
 * and this is a product people open while exhausted; the point is to be
 * calm and legible, not to be noticed.
 *
 * Opacity only, on the UI thread, and it respects reduced motion by holding
 * a steady mid-opacity instead of pulsing.
 */

import { useEffect } from 'react';
import { View, type ViewStyle } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { Ease } from '@/constants/motion';
import { Colors, Radius, Spacing } from '@/constants/theme';

const PULSE_MS = 900;

export function Skeleton({
  width = '100%',
  height = 14,
  radius = Radius.sm,
  style,
}: {
  width?: number | `${number}%`;
  height?: number;
  radius?: number;
  style?: ViewStyle;
}) {
  const pulse = useSharedValue(0.55);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) return;
    pulse.set(
      withRepeat(withTiming(1, { duration: PULSE_MS, easing: Ease.inOut }), -1, true),
    );
  }, [reduced, pulse]);

  const animated = useAnimatedStyle(() => ({ opacity: reduced ? 0.7 : pulse.get() }));

  return (
    <Animated.View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        { width, height, borderRadius: radius, backgroundColor: Colors.sidebarBg },
        style,
        animated,
      ]}
    />
  );
}

/**
 * The conversation's loading shape: a couple of exchanges, so the thread
 * looks like a thread before its content arrives.
 */
export function ConversationSkeleton() {
  return (
    <View style={{ padding: Spacing.md, gap: Spacing.lg }} accessibilityLabel="Loading your conversation">
      <View style={{ gap: Spacing.sm, alignItems: 'flex-end' }}>
        <Skeleton width="55%" height={38} radius={Radius.lg} />
      </View>
      <View style={{ gap: Spacing.sm }}>
        <Skeleton width="90%" />
        <Skeleton width="82%" />
        <Skeleton width="45%" />
      </View>
      <View style={{ gap: Spacing.sm, alignItems: 'flex-end' }}>
        <Skeleton width="40%" height={38} radius={Radius.lg} />
      </View>
      <View style={{ gap: Spacing.sm }}>
        <Skeleton width="88%" />
        <Skeleton width="60%" />
      </View>
    </View>
  );
}

/** A stack of list rows, for the drawer, My Care and the tool screens. */
export function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <View style={{ gap: Spacing.md }} accessibilityLabel="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <View key={i} style={{ flexDirection: 'row', gap: Spacing.md, alignItems: 'center' }}>
          <Skeleton width={38} height={38} radius={Radius.pill} />
          <View style={{ flex: 1, gap: 6 }}>
            <Skeleton width="55%" height={13} />
            <Skeleton width="80%" height={11} />
          </View>
        </View>
      ))}
    </View>
  );
}
