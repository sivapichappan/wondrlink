/**
 * Runtime env reader.
 *
 * Values live in app.json `expo.extra`. For production builds, override per
 * environment via EAS secrets or app.config.ts. For local dev, set them in
 * app.json or via process.env (Expo also reads EXPO_PUBLIC_* automatically).
 */

import Constants from 'expo-constants';

const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, string>;

function envOrExtra(key: string, fallback = ''): string {
  // EXPO_PUBLIC_* env vars are inlined at build time
  const fromEnv = process.env[`EXPO_PUBLIC_${key}`];
  if (fromEnv) return fromEnv;
  return extra[toCamel(key)] ?? fallback;
}

function toCamel(snake: string): string {
  return snake.toLowerCase().replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

export const env = {
  apiBase: envOrExtra('API_BASE', 'https://wondrlink-chat.vercel.app'),
  supabaseUrl: envOrExtra('SUPABASE_URL'),
  supabaseAnonKey: envOrExtra('SUPABASE_ANON_KEY'),
  sentryDsn: envOrExtra('SENTRY_DSN'),
} as const;
