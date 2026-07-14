/**
 * useModelerTrigger — fires the Modeler's end-of-conversation ping when the
 * user leaves a chat thread or backgrounds the app, but only if they actually
 * sent a message this session (otherwise there is nothing new to reason over).
 *
 * At most one ping per trigger event; the server debounce handles the rest.
 * Old clients without this hook are covered by the nightly cron.
 */

import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';

import { pingModeler } from '@/lib/api/modeler';

export function useModelerTrigger(messagesSentThisSession: number) {
  const sentRef = useRef(messagesSentThisSession);
  sentRef.current = messagesSentThisSession;
  const pingedOnBackgroundRef = useRef(false);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'background' && sentRef.current > 0 && !pingedOnBackgroundRef.current) {
        pingedOnBackgroundRef.current = true;
        void pingModeler();
      }
      if (state === 'active') {
        pingedOnBackgroundRef.current = false; // re-arm for the next backgrounding
      }
    });

    return () => {
      sub.remove();
      // Leaving the thread (unmount) counts as end-of-conversation too.
      if (sentRef.current > 0) void pingModeler();
    };
  }, []);
}
