/**
 * PressableScale — the app's press feedback, in one place.
 *
 * Before this existed the product had no press feedback worth the name: of
 * 88 Pressables, 60 did nothing at all on touch and the rest dimmed 15%.
 * There was not one scale in the app. On a phone there is no hover, so the
 * entire affordance a desktop puts in hover has to live in the press — and
 * a tap that produces no physical response reads as a dead button, which
 * people answer by tapping again.
 *
 * The scale takes the label and icons with it, and that is what makes it
 * read as pressing a thing rather than watching a colour change.
 *
 * Two implementation notes worth keeping:
 *
 * - NativeWind strips visual styles out of a `Pressable` style FUNCTION,
 *   which is why this app puts visuals on static inner Views and why press
 *   feedback never got built. Here the animation lives on an `Animated.View`
 *   carrying only `transform` and `opacity`, so there is nothing for
 *   NativeWind to strip and nothing for Yoga to re-lay-out.
 * - A shared value rather than a Reanimated CSS transition. The skill's
 *   default for a two-state toggle is a CSS transition, and that would be
 *   right for a one-off; this is the primitive underneath every tappable
 *   surface in the app, so it is worth paying six lines once to keep every
 *   press entirely off the JS thread with no re-render per tap.
 */

import { forwardRef } from 'react';
import {
  Pressable,
  View,
  type PressableProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import Animated, {
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';

import { Duration, Ease, PRESS_SCALE } from '@/constants/motion';

// `style` is deliberately narrowed off PressableProps: a Pressable accepts a
// style FUNCTION, and that function is exactly what NativeWind strips. Here
// the style lands on a plain Animated.View, so only a static style makes
// sense and the type says so.
interface Props extends Omit<PressableProps, 'style'> {
  children: React.ReactNode;
  /** Style for the animated wrapper. Visuals are fine here: it is a View. */
  style?: StyleProp<ViewStyle>;
  /** Override the press scale. 1 disables it (keeps the dim). */
  scaleTo?: number;
  /** How far it dims on press. */
  dim?: number;
}

export const PressableScale = forwardRef<View, Props>(function PressableScale(
  { children, style, scaleTo = PRESS_SCALE, dim = 0.12, disabled, ...rest },
  ref,
) {
  const progress = useSharedValue(0);
  const reduced = useReducedMotion();

  // Reduced motion means fewer and gentler, not none: the dim stays, because
  // it explains a state change; the movement goes.
  const targetScale = reduced ? 1 : scaleTo;

  const animatedStyle = useAnimatedStyle(() => {
    const p = progress.get();
    return {
      transform: [{ scale: 1 - p * (1 - targetScale) }],
      opacity: 1 - p * dim,
    };
  });

  const to = (value: number) => {
    'worklet';
    return withTiming(value, { duration: Duration.press, easing: Ease.out });
  };

  return (
    <Pressable
      ref={ref}
      disabled={disabled}
      // Feedback on press-IN, commit on press-out. Waiting for the tap to
      // complete before showing anything is the latency people actually feel.
      onPressIn={(e) => {
        if (!disabled) progress.set(to(1));
        rest.onPressIn?.(e);
      }}
      onPressOut={(e) => {
        progress.set(to(0));
        rest.onPressOut?.(e);
      }}
      // A finger drifting a few pixels should not cancel a press that was meant.
      pressRetentionOffset={rest.pressRetentionOffset ?? 12}
      {...rest}>
      <Animated.View style={[style, animatedStyle]}>{children}</Animated.View>
    </Pressable>
  );
});
