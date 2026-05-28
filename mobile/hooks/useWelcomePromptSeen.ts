/**
 * useWelcomePromptSeen — one-shot AsyncStorage flag for the first-launch
 * welcome modal on the chat screen.
 *
 * Mark seen the moment the user dismisses or actions the modal. We don't
 * re-show it. The persistent ProfileNudgeBanner keeps prompting them after
 * dismissal until they actually build a profile.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'wondrlink:welcome_prompt_seen';

export function useWelcomePromptSeen() {
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
