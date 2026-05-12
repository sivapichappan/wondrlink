/**
 * Sentry initialization.
 *
 * Called once from app/_layout.tsx. No-ops when SENTRY_DSN is unset so dev
 * builds don't spam an empty project.
 */

import * as Sentry from '@sentry/react-native';
import { env } from './env';

let initialized = false;

export function initSentry() {
  if (initialized) return;
  if (!env.sentryDsn) {
    if (__DEV__) console.log('[sentry] SENTRY_DSN unset — skipping init');
    return;
  }
  Sentry.init({
    dsn: env.sentryDsn,
    enableAutoSessionTracking: true,
    sendDefaultPii: false,
    tracesSampleRate: 0.2,
  });
  initialized = true;
}

export { Sentry };
