/**
 * Tapping a notification should open the thing it is about.
 *
 * Until now nothing listened, so a tap just opened the app to wherever it was
 * last — which for "your answer is ready" means being told an answer exists and
 * then having to go find it.
 *
 * TWO WAYS IN, and both are needed. A running app gets a response event. An app
 * launched cold BY the tap has already missed that event, so the last response
 * has to be read once at startup instead.
 *
 * IT MUST NOT RACE THE AUTH GATE. RootGate redirects an unauthenticated app to
 * (auth)/welcome, and a cold launch resolves the session a moment after the
 * notification is read. Navigating first means being bounced straight back out,
 * so the target is parked and replayed once there is a session.
 */

import * as Notifications from 'expo-notifications';
import { useRouter } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';

type NotificationData = Record<string, unknown>;

/** Which route a notification's payload points at, or null for none. */
function routeFor(data: NotificationData | undefined): string | null {
  if (!data) return null;
  const kind = typeof data.kind === 'string' ? data.kind : null;
  const conversationId =
    typeof data.conversation_id === 'string' ? data.conversation_id : null;

  if (kind === 'answer_ready' && conversationId) return `/chat/${conversationId}`;
  if (kind === 'reviewer_approved' || kind === 'reviewer_rejected') return '/';
  return null;
}

export function useNotificationRouting(hasSession: boolean) {
  const router = useRouter();
  const parked = useRef<string | null>(null);
  const handledColdStart = useRef(false);

  const go = useCallback(
    (route: string | null) => {
      if (!route) return;
      if (!hasSession) {
        parked.current = route;
        return;
      }
      router.push(route as never);
    },
    [hasSession, router],
  );

  // Cold start: the tap that launched the app already happened.
  useEffect(() => {
    if (handledColdStart.current) return;
    handledColdStart.current = true;
    Notifications.getLastNotificationResponseAsync()
      .then((response) => {
        const data = response?.notification?.request?.content?.data as NotificationData;
        go(routeFor(data));
      })
      .catch(() => {});
  }, [go]);

  // Running app: a tap while we are alive.
  useEffect(() => {
    const sub = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response?.notification?.request?.content?.data as NotificationData;
      go(routeFor(data));
    });
    return () => sub.remove();
  }, [go]);

  // The session arrived after a parked target. Replay it now.
  useEffect(() => {
    if (!hasSession || !parked.current) return;
    const route = parked.current;
    parked.current = null;
    router.push(route as never);
  }, [hasSession, router]);
}
