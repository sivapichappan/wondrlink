/**
 * useGuardedSend — the single crisis-guardrail choke point for chat sends.
 *
 * Extracted verbatim from the old chat screen so EVERY send path (Home → thread
 * hand-off, thread composer, follow-up chips, quick actions) funnels through the
 * identical scan → CrisisModal → Sentry-on-override flow. App Store reviewers
 * explicitly look for this; never call a raw sendMessage directly.
 *
 * Usage:
 *   const { guardedSend, crisis, continueCrisis, closeCrisis } = useGuardedSend(send);
 *   ...
 *   <CrisisModal category={crisis?.hit.category ?? null}
 *                onContinue={continueCrisis} onClose={closeCrisis} />
 */

import { useCallback, useState } from 'react';

import { scanForCrisis, type GuardrailHit } from '@/lib/safety/crisis-keywords';
import { Sentry } from '@/lib/sentry';

interface CrisisState {
  hit: GuardrailHit;
  pending: string;
}

export function useGuardedSend(send: (text: string) => void) {
  const [crisis, setCrisis] = useState<CrisisState | null>(null);

  const guardedSend = useCallback(
    (text: string) => {
      const hit = scanForCrisis(text);
      if (hit) {
        setCrisis({ hit, pending: text });
        return;
      }
      send(text);
    },
    [send],
  );

  const continueCrisis = useCallback(() => {
    setCrisis((c) => {
      if (!c) return null;
      Sentry.captureMessage('crisis-guardrail-overridden', {
        level: 'warning',
        tags: { category: c.hit.category, matched: c.hit.matched },
      });
      send(c.pending);
      return null;
    });
  }, [send]);

  const closeCrisis = useCallback(() => setCrisis(null), []);

  return { guardedSend, crisis, continueCrisis, closeCrisis };
}
