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

/**
 * Best-effort E.164 normalization (US default for bare 10-digit numbers),
 * mirroring the retired backend helper.
 */
function normalizePhone(phone: string): string | null {
  let digits = phone.replace(/\D/g, '');
  if (digits.length === 10) digits = `1${digits}`;
  if (digits.length < 11 || digits.length > 15) return null;
  return `+${digits}`;
}

function friendlyPhoneError(message: string): string {
  const m = message.toLowerCase();
  if (m.includes('not enabled') || m.includes('disabled') || m.includes('unsupported')) {
    return 'Phone sign-in is not available yet. Please use email for now.';
  }
  if (m.includes('rate')) {
    return 'Too many codes requested. Please wait a few minutes and try again.';
  }
  return message;
}

/**
 * Sage phone sign-in step 1: text a one-time code to the number.
 *
 * Guidelines hard rule: the client talks ONLY to Supabase auth for OTP —
 * no backend proxy, no provider knowledge. During dev, Supabase dashboard
 * TEST phone numbers (static codes) make this work with no SMS provider;
 * at launch Twilio Verify plugs into the same dashboard setting with zero
 * client change.
 */
export async function sendPhoneCode(phone: string) {
  const normalized = normalizePhone(phone);
  if (!normalized) throw new Error('Please enter a valid phone number.');
  const { error } = await supabase.auth.signInWithOtp({ phone: normalized });
  if (error) throw new Error(friendlyPhoneError(error.message));
  return { status: 'ok' as const, message: 'Code sent.' };
}

/** Sage phone sign-in step 2: verify the code; first-time numbers become accounts. */
export async function verifyPhoneCode(phone: string, code: string) {
  const normalized = normalizePhone(phone);
  if (!normalized) throw new Error('Please enter a valid phone number.');
  const { data, error } = await supabase.auth.verifyOtp({
    phone: normalized,
    token: code.trim(),
    type: 'sms',
  });
  if (error) throw new Error(friendlyPhoneError(error.message));
  if (!data.session || !data.user) {
    throw new NoSessionError('Could not start a session. Please try again.');
  }
  // supabase-js stores the session itself (AsyncStorage + auto-refresh);
  // no setSession plumbing needed on this path.
  return { user_id: data.user.id, email: data.user.email ?? '' };
}

/**
 * Resend the signup confirmation email. Called from the "check your
 * email" success screen so users who didn't receive the original email
 * can request another. Supabase rate-limits aggressively — surface the
 * generic "we tried again" message either way.
 */
export async function resendSignupConfirmation(email: string) {
  const { error } = await supabase.auth.resend({
    type: 'signup',
    email: email.trim(),
  });
  if (error) throw error;
}

export async function logout() {
  try {
    await apiFetch(ENDPOINTS.authLogout, { method: 'POST' });
  } catch {
    // ignore — Supabase signOut is the source of truth
  }
  await supabase.auth.signOut();
}
