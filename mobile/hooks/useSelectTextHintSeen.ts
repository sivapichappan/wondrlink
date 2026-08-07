/**
 * useSelectTextHintSeen — one-shot flag for the "press and hold" hint.
 *
 * Selecting part of a message happens in a sheet, because React Native cannot
 * select inside a rendered message on iOS (see SelectTextSheet). That makes the
 * gesture the only way in, and an invisible gesture is a feature nobody finds.
 *
 * Cleared on the first successful long press rather than on first render: the
 * hint is there to teach the gesture, so it should survive until the gesture
 * has actually been used once.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'wondrlink:selecthint_seen';

export function useSelectTextHintSeen() {
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
