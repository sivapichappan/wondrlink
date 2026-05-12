/**
 * Auth API wrappers.
 *
 * Uses the backend's /api/auth/* endpoints (rate-limited) rather than calling
 * Supabase JS directly. The backend returns access_token + refresh_token,
 * which we plug into Supabase JS via setSession() so AsyncStorage persists
 * the session and all future apiFetch calls carry the Bearer token.
 */

import { ENDPOINTS } from '@shared/api-contracts';

import { apiFetch } from './client';
import { supabase } from '../supabase';

interface AuthSuccessBody {
  status: 'ok';
  message: string;
  user: { user_id: string; email: string };
  access_token: string;
  refresh_token: string;
}

async function plugIntoSupabase(body: AuthSuccessBody) {
  await supabase.auth.setSession({
    access_token: body.access_token,
    refresh_token: body.refresh_token,
  });
  return body.user;
}

export async function register(email: string, password: string) {
  const body = await apiFetch<AuthSuccessBody>(ENDPOINTS.authRegister, {
    method: 'POST',
    skipAuth: true,
    body: { email: email.trim(), password },
  });
  return plugIntoSupabase(body);
}

export async function login(email: string, password: string) {
  const body = await apiFetch<AuthSuccessBody>(ENDPOINTS.authLogin, {
    method: 'POST',
    skipAuth: true,
    body: { email: email.trim(), password },
  });
  return plugIntoSupabase(body);
}

export async function logout() {
  try {
    await apiFetch(ENDPOINTS.authLogout, { method: 'POST' });
  } catch {
    // ignore — Supabase signOut is the source of truth
  }
  await supabase.auth.signOut();
}
