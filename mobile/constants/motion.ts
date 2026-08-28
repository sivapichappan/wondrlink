/**
 * Motion tokens.
 *
 * Every duration, curve and spring in the app comes from here. The rule is
 * the same one that governs `theme.ts`: no approximated values at call
 * sites, because a codebase with fourteen slightly different easings reads
 * as fourteen different products.
 *
 * Two constraints shape all of it, and they are specific to this app:
 *
 *   1. The person holding the phone is frightened and tired. Motion here
 *      exists to keep a change from being jarring and to confirm a touch
 *      landed. It never exists to be admired. There is no celebration
 *      budget in this file, deliberately: the rare high-emotion moments in
 *      a cancer app are usually bad news, and a flourish next to a
 *      prognosis wall would be indefensible.
 *   2. Everything must survive a release build on the slowest phone we
 *      support. That means `transform` and `opacity` only, on the UI
 *      thread, always.
 *
 * Reanimated 4 only. Core `Animated` cannot be driven by a gesture without
 * crossing the bridge, and `useNativeDriver` refuses anything but transform
 * and opacity anyway.
 */

import {
  Easing,
  FadeIn,
  FadeInDown,
  FadeOutDown,
  ReduceMotion,
} from 'react-native-reanimated';

/**
 * Curves. Reanimated's built-in easings are as weak as CSS's, so these are
 * explicit béziers.
 *
 * Never `ease-in` on UI: it starts slow, which delays the exact moment the
 * user is watching for a response.
 */
export const Ease = {
  /** Entering, exiting, and the default for anything without a finger on it. */
  out: Easing.bezier(0.23, 1, 0.32, 1),
  /** Something moving or morphing while already on screen. */
  inOut: Easing.bezier(0.77, 0, 0.175, 1),
  /** The iOS sheet curve, for anything that behaves like a sheet. */
  sheet: Easing.bezier(0.32, 0.72, 0, 1),
  /** Constant motion only: progress, marquee. */
  linear: Easing.linear,
} as const;

/**
 * Durations. Mobile UI motion stays under 300ms; the platform's own
 * transitions are longer and we match the platform for navigation rather
 * than overriding it.
 */
export const Duration = {
  /** Press feedback. Above ~150ms a press stops feeling like a press. */
  press: 120,
  /** A toggle, a chip, a small state change. */
  state: 180,
  /** Something entering or leaving the conversation. */
  enter: 220,
  /** A sheet or drawer, when a timing curve is used rather than a spring. */
  sheet: 300,
} as const;

/**
 * Springs, in Reanimated's two-parameter form (Apple's designer parameters)
 * rather than mass/stiffness/damping.
 *
 * If a finger was involved, use a spring: springs carry velocity through an
 * interruption, timing curves restart from zero. Bounce belongs only where
 * the gesture actually carried momentum.
 */
export const Spring = {
  /** Default settle. Critically damped, so it never overshoots. */
  settle: { duration: 400, dampingRatio: 1 } as const,
  /** Snapping back or repositioning after a drag. Pass the release velocity. */
  snap: { duration: 400, dampingRatio: 0.8 } as const,
  /** A sheet or drawer following, then leaving, a finger. */
  sheet: { duration: 300, dampingRatio: 0.8 } as const,
} as const;

/**
 * Reduced motion is shipped with each animation, never as a follow-up.
 *
 * It means fewer and gentler, not none: opacity and colour changes that
 * explain a state change stay, while translation, scale and overshoot go.
 * `ReduceMotion.System` lets each animation follow the OS setting.
 */
export const REDUCE_MOTION = ReduceMotion.System;

/**
 * How far something rises as it enters. Small on purpose: this is a hint
 * that content arrived, not a performance.
 */
export const ENTER_TRANSLATE_Y = 8;

/**
 * Press scale. Takes the label and icons with it, which is what makes a
 * press read as physical rather than as a colour change.
 *
 * Never `scale(0)` anywhere in the app, entering or leaving: nothing in the
 * real world appears from nothing.
 */
export const PRESS_SCALE = 0.97;

/**
 * How something Sage deals arrives, and how it leaves.
 *
 * A short rise and settle, never a pop: it starts at 0.97 and 8px low, not
 * at zero. Exit mirrors entry, because a card that arrives from below and
 * then vanishes in place reads as a glitch rather than as being put away.
 *
 * Built as functions because a Reanimated layout-animation builder is
 * stateful and must not be shared between mounted components.
 */
export function cardEnter() {
  return FadeInDown.duration(Duration.enter)
    .easing(Ease.out)
    .withInitialValues({ transform: [{ translateY: ENTER_TRANSLATE_Y }, { scale: 0.97 }] })
    .reduceMotion(REDUCE_MOTION);
}

export function cardExit() {
  return FadeOutDown.duration(Duration.state)
    .easing(Ease.out)
    .reduceMotion(REDUCE_MOTION);
}

/** A message arriving in the thread. Quieter than a card: it is just speech. */
export function messageEnter() {
  return FadeIn.duration(Duration.state).easing(Ease.out).reduceMotion(REDUCE_MOTION);
}
