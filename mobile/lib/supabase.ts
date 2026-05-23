/**
 * Supabase client.
 *
 * Uses AsyncStorage as the session store so users stay logged in across app
 * launches. Auth is the SAME Supabase project as the web app — JWTs issued
 * here will Authorize the Flask backend's `/api/*` endpoints identically.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { env } from './env';

const hasCreds = !!env.supabaseUrl && !!env.supabaseAnonKey;
if (!hasCreds) {
  console.warn(
    '[supabase] Missing SUPABASE_URL or SUPABASE_ANON_KEY. ' +
      'Auth + API calls will fail until you set them in app.json `expo.extra` ' +
      'or as EXPO_PUBLIC_* env vars. Booting with placeholders so the UI can render.',
  );
}

// Placeholders let the app boot for UI preview; real network ops will fail
// (which the UI handles via ApiError + offline-style fallbacks).
const url = hasCreds ? env.supabaseUrl : 'https://placeholder.supabase.co';
const key = hasCreds ? env.supabaseAnonKey : 'placeholder-anon-key';

export const supabase = createClient(url, key, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});
