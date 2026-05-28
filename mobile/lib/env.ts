/**
 * Runtime env reader.
 *
 * `EXPO_PUBLIC_*` vars are inlined by Metro at build time — but only when
 * read STATICALLY (e.g. `process.env.EXPO_PUBLIC_API_BASE`). Dynamic lookups
 * like `process.env[`EXPO_PUBLIC_${key}`]` are NOT inlined, which is why we
 * write each read explicitly here.
 *
 * Order of resolution per field:
 *   1. EXPO_PUBLIC_* env var (set in EAS environment or .env.local)
 *   2. Constants.expoConfig.extra (app.json fallback)
 *   3. Hardcoded fallback
 */

import Constants from 'expo-constants';

const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, string>;

function pick(envValue: string | undefined, extraValue: string | undefined, fallback = ''): string {
  if (envValue && envValue.length > 0) return envValue;
  if (extraValue && extraValue.length > 0) return extraValue;
  return fallback;
}

export const env = {
  apiBase: pick(
    process.env.EXPO_PUBLIC_API_BASE,
    extra.apiBase,
    'https://wondrchat.vercel.app',
  ),
  supabaseUrl: pick(process.env.EXPO_PUBLIC_SUPABASE_URL, extra.supabaseUrl),
  supabaseAnonKey: pick(process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY, extra.supabaseAnonKey),
  sentryDsn: pick(process.env.EXPO_PUBLIC_SENTRY_DSN, extra.sentryDsn),
} as const;
