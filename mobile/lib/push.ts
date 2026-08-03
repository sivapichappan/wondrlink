/**
 * Registering this device for push notifications.
 *
 * WHEN TO ASK. Not at sign-in. A permission prompt fired at launch, before the
 * person has any idea what would be sent, is the reliable way to get a "no" you
 * can never ask again for — iOS gives you exactly one system prompt, and after a
 * denial the only route back is Settings. So the ask happens at the one moment
 * the answer is obviously useful: right after a clinician submits a reviewer
 * application, when the whole question on their mind is "how will I know?"
 *
 * EVERY FUNCTION HERE IS BEST-EFFORT AND NEVER THROWS. Push is a nicety layered
 * on top of state the app already reads on every launch. Nothing about
 * applying, approving, or using the app may fail because a token could not be
 * minted — a simulator has no push capability at all, and that must not look
 * like a broken application form.
 *
 * The module is imported normally rather than behind a lazy require. Both
 * packages are in the binary from build #35 on, and a try/catch around a lazy
 * require CANNOT contain a throwing native module anyway: Metro's
 * guardedLoadModule catches the factory's throw itself and reports it as fatal
 * (see .claude/rules/mobile-ui.md). The safe pattern is to ship the pod, which
 * we now do.
 */

import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { ENDPOINTS } from '@shared/api-contracts';

import { apiFetch } from './api/client';

/** A notification arriving while the app is open should still be seen: the
 *  approval is the thing the person is sitting there waiting for. */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export type PushPermission = 'granted' | 'denied' | 'unavailable';

/** Whether iOS has already been asked, without asking. Lets a screen show the
 *  right thing instead of guessing. */
export async function pushPermissionStatus(): Promise<PushPermission> {
  try {
    if (!Device.isDevice) return 'unavailable';
    const { status } = await Notifications.getPermissionsAsync();
    return status === 'granted' ? 'granted' : 'denied';
  } catch {
    return 'unavailable';
  }
}

/**
 * Ask for permission if it has not been asked, mint a token, and send it to the
 * server. Returns what happened so a screen can say something true about it.
 *
 * Safe to call more than once: the server upserts on (user, token), and iOS
 * returns the existing grant rather than re-prompting.
 */
export async function registerForPush(): Promise<PushPermission> {
  try {
    // A simulator cannot receive push at all. Asking there produces a
    // confusing prompt and then a failure that means nothing.
    if (!Device.isDevice) return 'unavailable';

    const existing = await Notifications.getPermissionsAsync();
    let status = existing.status;
    if (status !== 'granted') {
      // THE one system prompt. Never called from a launch path.
      const asked = await Notifications.requestPermissionsAsync();
      status = asked.status;
    }
    if (status !== 'granted') return 'denied';

    // projectId is required on SDK 49+ or this throws at runtime in a
    // standalone build while working fine in Expo Go.
    const projectId = '2635ff08-2298-49d8-af77-f10bc4fe6ea5';
    const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
    if (!token) return 'denied';

    await apiFetch<{ status: 'ok' }>(ENDPOINTS.pushRegister, {
      method: 'POST',
      body: { token, platform: Platform.OS === 'ios' ? 'ios' : 'android' },
    });
    return 'granted';
  } catch {
    // Includes the device having no push entitlement, no network, and the
    // server not yet carrying the endpoint. None of those are the caller's
    // problem.
    return 'unavailable';
  }
}

/**
 * Forget this device's token. Called on sign-out: a shared or handed-on phone
 * must not keep receiving notifications for an account nobody is signed into.
 */
export async function unregisterPush(): Promise<void> {
  try {
    if (!Device.isDevice) return;
    const { status } = await Notifications.getPermissionsAsync();
    if (status !== 'granted') return;
    const projectId = '2635ff08-2298-49d8-af77-f10bc4fe6ea5';
    const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
    if (!token) return;
    await apiFetch<{ status: 'ok' }>(ENDPOINTS.pushUnregister, {
      method: 'POST',
      body: { token },
    });
  } catch {
    // Best effort. The server also drops a token Expo reports as dead.
  }
}
