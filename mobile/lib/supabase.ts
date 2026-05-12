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

if (!env.supabaseUrl || !env.supabaseAnonKey) {
  console.warn(
    '[supabase] Missing SUPABASE_URL or SUPABASE_ANON_KEY. ' +
      'Set them in app.json `expo.extra` or as EXPO_PUBLIC_* env vars.',
  );
}

export const supabase = createClient(env.supabaseUrl, env.supabaseAnonKey, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});
