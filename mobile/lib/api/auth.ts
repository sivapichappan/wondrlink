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
  // Both can be null when Supabase requires email confirmation — the user
  // exists but there's no session yet. plugIntoSupabase throws
  // NoSessionError in that case so the UI can surface a "check your email"
  // message rather than silently dropping the user into a session-less app.
  access_token: string | null;
  refresh_token: string | null;
}

/** Thrown when register/login succeeds at the API layer but Supabase
 *  didn't return a session (typically: email confirmation enabled). */
export class NoSessionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NoSessionError';
  }
}

async function plugIntoSupabase(body: AuthSuccessBody) {
  if (!body.access_token || !body.refresh_token) {
    throw new NoSessionError(
      'Account created. Please check your email for a verification link, then sign in.',
    );
  }
  const { error } = await supabase.auth.setSession({
    access_token: body.access_token,
    refresh_token: body.refresh_token,
  });
  if (error) {
    throw new NoSessionError(error.message ?? 'Could not start a session. Please try signing in again.');
  }
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
