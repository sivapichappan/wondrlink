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
 * Resend the signup confirmation email. Called from the code-entry screen so
 * users who didn't receive the original email can request another. Supabase
 * rate-limits aggressively — surface the generic "we tried again" message
 * either way.
 */
export async function resendSignupConfirmation(email: string) {
  const { error } = await supabase.auth.resend({
    type: 'signup',
    email: email.trim(),
  });
  if (error) throw error;
}

/* -------------------------------------------------------------------------
 * Email codes.
 *
 * Sign-up and password reset both confirm by six-digit code rather than by
 * clicking a link. That is a property of the EMAIL TEMPLATE, not of the calls
 * below: Supabase sends a code only where the template contains {{ .Token }},
 * and a link where it contains {{ .ConfirmationURL }}. The two templates that
 * must carry {{ .Token }} live in config/email_templates/ and are pasted into
 * the Supabase dashboard — see that directory's README. If someone reverts a
 * template to the link version, these calls keep working and users get a link
 * with no code in it, so the templates are covered by a test.
 *
 * Verify runs against supabase-js directly rather than the Flask API, matching
 * the phone path: the client talks only to Supabase auth for one-time codes.
 * Sign-up itself still goes through the backend, which holds the IP rate limit
 * and the region geofence.
 * ---------------------------------------------------------------------- */

/**
 * How many digits the emailed code has.
 *
 * MUST match Supabase's **Email OTP Length** (Authentication → Sign In /
 * Providers → Email), which is configurable from 6 to 10. It is 8 on this
 * project. Every screen and every message reads this rather than spelling a
 * number, because the length was written into six separate places and the web
 * form capped its input at 6 — which silently truncated a real code to
 * something that could never verify.
 *
 * Change the dashboard setting and change this, together.
 */
export const EMAIL_CODE_LENGTH = 8;

function friendlyEmailCodeError(message: string): string {
  const m = message.toLowerCase();
  // The built-in Supabase SMTP refuses every address outside the project's own
  // team until custom SMTP is configured. Without this branch the user reads
  // "Email address not authorized" and has no idea what to do.
  if (m.includes('not authorized')) {
    return 'We cannot send email to that address yet. Please use phone sign-in for now.';
  }
  if (m.includes('expired')) {
    return 'That code has expired. Ask for a new one.';
  }
  if (m.includes('invalid') || m.includes('token')) {
    return 'That code did not work. Please check it and try again.';
  }
  if (m.includes('rate') || m.includes('too many') || m.includes('security purposes')) {
    return 'Too many tries. Please wait a few minutes and try again.';
  }
  return message;
}

/**
 * Sign-up step 2: confirm the emailed code. `type: 'signup'` is the confirm
 * signup token, which is what sign_up() sends — NOT 'email' (a magic-link or
 * passwordless OTP) and NOT 'recovery' (a password reset).
 */
export async function verifySignupCode(email: string, code: string) {
  const { data, error } = await supabase.auth.verifyOtp({
    email: email.trim(),
    token: code.trim(),
    type: 'signup',
  });
  if (error) throw new Error(friendlyEmailCodeError(error.message));
  if (!data.session || !data.user) {
    throw new NoSessionError('Could not start a session. Please try signing in.');
  }
  // supabase-js persists the session itself (AsyncStorage + auto-refresh).
  return { user_id: data.user.id, email: data.user.email ?? '' };
}

/**
 * Forgot password step 1: email a reset code.
 *
 * Never reveals whether the address has an account — Supabase returns success
 * for unknown addresses by design, and the UI must not add that distinction
 * back by treating an error differently.
 */
export async function sendPasswordResetCode(email: string) {
  const { error } = await supabase.auth.resetPasswordForEmail(email.trim());
  if (error) throw new Error(friendlyEmailCodeError(error.message));
}

/** Forgot password step 2: exchange the code for a short-lived session. */
export async function verifyPasswordResetCode(email: string, code: string) {
  const { data, error } = await supabase.auth.verifyOtp({
    email: email.trim(),
    token: code.trim(),
    type: 'recovery',
  });
  if (error) throw new Error(friendlyEmailCodeError(error.message));
  if (!data.session) {
    throw new NoSessionError('Could not verify that code. Please try again.');
  }
}

/**
 * Forgot password step 3: set the new password.
 *
 * Requires the session that verifyPasswordResetCode just established, which is
 * why the two cannot be reordered.
 */
export async function setNewPassword(password: string) {
  const { error } = await supabase.auth.updateUser({ password });
  if (error) throw new Error(friendlyEmailCodeError(error.message));
}

/**
 * Mirrors the server's password rules (lib/auth_helpers.py register_user) so a
 * weak password is caught before a round trip. The SERVER stays authoritative;
 * this only saves the user a rejected submit. Keep the two in step.
 */
export function passwordProblem(password: string): string | null {
  if (password.length < 8) return 'Please use at least 8 characters.';
  if (!/[A-Z]/.test(password)) return 'Please include one capital letter.';
  if (!/[a-z]/.test(password)) return 'Please include one lowercase letter.';
  if (!/[0-9]/.test(password)) return 'Please include one number.';
  return null;
}

export async function logout() {
  // Drop this device's push token FIRST, while the session still exists to
  // authorise the call. A handed-on or shared phone must not keep receiving
  // notifications for an account nobody is signed into.
  //
  // Here rather than at the call sites: there are eight of them, and the ninth
  // would forget. Best-effort by construction — unregisterPush never throws,
  // and a failure here must not strand someone in a session they asked to
  // leave.
  try {
    const { unregisterPush } = await import('../push');
    await unregisterPush();
  } catch {
    // ignore — the server also drops a token Expo reports as dead
  }
  try {
    await apiFetch(ENDPOINTS.authLogout, { method: 'POST' });
  } catch {
    // ignore — Supabase signOut is the source of truth
  }
  await supabase.auth.signOut();
}
