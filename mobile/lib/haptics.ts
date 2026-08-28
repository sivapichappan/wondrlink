/**
 * Haptics.
 *
 * `expo-haptics` has been a dependency of this app for months with zero
 * imports. Mobile has a sense the web does not, and used sparingly it is
 * the thing that makes an app feel considered; used everywhere, people turn
 * it off in Settings and you lose it for the moments that mattered.
 *
 * Named by MOMENT rather than by intensity, so no call site ever has to
 * choose between Light and Medium and get it subtly wrong on one screen.
 *
 * Three rules, and they are absolute:
 *
 *   1. Same frame as the visual. A haptic that lags its animation reads as
 *      a glitch rather than as feedback, so it fires at the causal moment
 *      (the chip being chosen), not when the animation finishes.
 *   2. One per user action. Never on scroll, never per frame, never on an
 *      entrance the user did not cause.
 *   3. Never the only feedback. Haptics are off system-wide for many people
 *      and silent on most Android hardware, so the visual always stands
 *      alone.
 *
 * And one rule specific to this product: NOTHING FIRES ON A CRISIS CARD.
 * A buzz against "This is an emergency. Call 911 now." is the wrong
 * register for the worst moment of someone's day, and it is the one place
 * where a flourish would be actively harmful. `notifyError` exists for a
 * failed request, not for bad news.
 *
 * Every call is fire-and-forget and can never throw: a device without a
 * taptic engine, or a user who has switched it off, must not be able to
 * break a send.
 */

import * as Haptics from 'expo-haptics';

function safely(run: () => Promise<unknown>): void {
  try {
    void run().catch(() => {});
  } catch {
    // No taptic engine, permission denied, platform without support.
  }
}

/**
 * A value ticked past a step: a chip chosen, a picker detent, a segmented
 * control moving. The lightest thing available, for the most frequent use.
 */
export function selection(): void {
  safely(() => Haptics.selectionAsync());
}

/** Something snapped home: a card dismissed, a drawer catching its edge. */
export function snap(): void {
  safely(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
}

/** A heavier landing, or a destructive action committing. */
export function commit(): void {
  safely(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
}

/** An operation the user asked for finished. Not for good news, for done. */
export function notifySuccess(): void {
  safely(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
}

/**
 * An operation FAILED: the send did not go through, the save was rejected.
 * Never for a clinical finding, never on a crisis card.
 */
export function notifyError(): void {
  safely(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error));
}
