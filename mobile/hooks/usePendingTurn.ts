/**
 * The question we are still waiting on, remembered across app launches.
 *
 * Everything else about a send lives in memory: the optimistic bubble is in the
 * React Query cache, the mutation is in a component. iOS suspending the app is
 * survivable for those, but being killed outright is not — and either way the
 * in-flight request is gone while the server carries on and finishes.
 *
 * So the turn is written to disk BEFORE the request goes out. Coming back to
 * the app, even from a cold start, there is a record saying "you asked
 * something and never saw the answer", and an id to go and fetch it with.
 *
 * One at a time is enough: the composer is disabled while a send is in flight.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'wondrlink:pending_turn';

export interface PendingTurn {
  clientTurnId: string;
  /** Null for a thread that had no id yet; the server assigns one. */
  conversationId: string | null;
  /** Kept so a cold start can show what was asked while it recovers. */
  question: string;
  /** ms epoch, for the recovery deadline. */
  startedAt: number;
}

/** Server maxDuration is 60s; this leaves room for a cold start on top. */
export const RECOVERY_DEADLINE_MS = 120_000;

export function usePendingTurn() {
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (!raw) return;
        try {
          const parsed = JSON.parse(raw) as PendingTurn;
          // A turn older than the deadline was never going to arrive. Drop it
          // rather than greeting someone with a stale "still working".
          if (Date.now() - parsed.startedAt < RECOVERY_DEADLINE_MS) setPending(parsed);
          else AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
        } catch {
          AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
        }
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const begin = useCallback((turn: PendingTurn) => {
    setPending(turn);
    // Deliberately not awaited: the request must not wait on a disk write.
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(turn)).catch(() => {});
  }, []);

  const clear = useCallback(() => {
    setPending(null);
    AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
  }, []);

  return { pending, loaded, begin, clear };
}
