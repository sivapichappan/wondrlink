/**
 * useWatchlist — AsyncStorage-backed list of saved clinical trials.
 * Mirrors the web app's `wondrlink_trial_watchlist` localStorage key in
 * spirit (not bit-for-bit; mobile is its own client).
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { sendTrialFeedback } from '@/lib/api/trials';

const STORAGE_KEY = 'wondrlink:trial_watchlist';

export interface SavedTrial {
  nct_id: string;
  title: string;
  phase?: string;
  url?: string;
  saved_at: string;
}

interface Hook {
  trials: SavedTrial[];
  loaded: boolean;
  isSaved: (nctId: string) => boolean;
  save: (trial: Omit<SavedTrial, 'saved_at'>) => void;
  remove: (nctId: string) => void;
  clear: () => void;
}

export function useWatchlist(): Hook {
  const [trials, setTrials] = useState<SavedTrial[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (raw) {
          try {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) setTrials(parsed);
          } catch {
            // corrupt — reset
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const persist = useCallback((next: SavedTrial[]) => {
    setTrials(next);
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
  }, []);

  const isSaved = useCallback(
    (nctId: string) => trials.some((t) => t.nct_id === nctId),
    [trials],
  );

  const save = useCallback(
    (trial: Omit<SavedTrial, 'saved_at'>) => {
      if (trials.some((t) => t.nct_id === trial.nct_id)) return;
      persist([{ ...trial, saved_at: new Date().toISOString() }, ...trials]);
      void sendTrialFeedback(trial.nct_id, 'saved'); // fire-and-forget telemetry
    },
    [trials, persist],
  );

  const remove = useCallback(
    (nctId: string) => {
      persist(trials.filter((t) => t.nct_id !== nctId));
      void sendTrialFeedback(nctId, 'removed');
    },
    [trials, persist],
  );

  const clear = useCallback(() => persist([]), [persist]);

  return { trials, loaded, isSaved, save, remove, clear };
}
