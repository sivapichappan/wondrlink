/**
 * useNotifyOfferSeen — the "want a nudge next time?" card is offered once.
 *
 * Marked seen whichever way they answer, including "no thanks". iOS allows one
 * permission prompt per install, so a declined offer is a settled question, not
 * one to raise again on the next recovery. Settings keeps a permanent row for
 * anyone who changes their mind.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'wondrlink:notify_offer_seen';

export function useNotifyOfferSeen() {
  const [seen, setSeen] = useState<boolean | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((v) => setSeen(v === '1'))
      .catch(() => setSeen(false));
  }, []);

  const markSeen = useCallback(() => {
    setSeen(true);
    AsyncStorage.setItem(STORAGE_KEY, '1').catch(() => {});
  }, []);

  return { seen, markSeen };
}
