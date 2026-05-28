/**
 * useResponseLength — persisted Brief/Normal/Detailed preference.
 *
 * Mirrors the web app's "Detail Level" dropdown. Stored in AsyncStorage so
 * the choice survives app restarts and is shared by every chat request.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import type { ResponseLength } from '@shared/types';

const STORAGE_KEY = 'wondrlink:response_length';
const DEFAULT: ResponseLength = 'normal';

export function useResponseLength() {
  const [value, setValue] = useState<ResponseLength>(DEFAULT);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((v) => {
        if (v === 'brief' || v === 'normal' || v === 'detailed') setValue(v);
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const update = useCallback((next: ResponseLength) => {
    setValue(next);
    AsyncStorage.setItem(STORAGE_KEY, next).catch(() => {});
  }, []);

  return { responseLength: value, setResponseLength: update, loaded };
}
