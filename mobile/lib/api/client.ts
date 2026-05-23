/**
 * API fetch wrapper.
 *
 * - Attaches the current Supabase JWT as `Authorization: Bearer <token>`.
 * - Resolves endpoint paths against env.apiBase.
 * - Throws ApiError with parsed body on non-2xx responses so call sites can
 *   distinguish 400 (validation) from 422 (blocked state) from 5xx.
 *
 * Higher-level wrappers (lib/api/chat.ts, lib/api/auth.ts, etc.) live alongside
 * this file and import `apiFetch`.
 */

import { env } from '../env';
import { supabase } from '../supabase';
import type { ApiErrorBody } from '@shared/types';

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null, message?: string) {
    super(message ?? extractErrorMessage(body, `Request failed with ${status}`));
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/**
 * Safely extract a human-readable error string from any value.
 *
 * Handles:
 *   - string: returned as-is
 *   - { error: string }: returns the error
 *   - { error: { message } }: returns the message (Supabase AuthError shape)
 *   - { message }: returns the message
 *   - anything else: returns the fallback
 *
 * Use this whenever you setError() with a value that could come from a
 * remote source. Avoids the "Objects are not valid as a React child"
 * crash when an error body comes back in an unexpected shape (e.g.
 * Supabase auth errors leaking through the Flask wrapper).
 */
export function extractErrorMessage(input: unknown, fallback: string): string {
  if (input == null) return fallback;
  if (typeof input === 'string') return input;
  if (typeof input === 'object') {
    const o = input as Record<string, unknown>;
    // ApiErrorBody — `error` field is the user-facing message (usually a string,
    // but some Supabase errors come through as { code, message }).
    if ('error' in o) {
      const err = o.error;
      if (typeof err === 'string') return err;
      if (err && typeof err === 'object' && 'message' in err && typeof (err as any).message === 'string') {
        return (err as any).message;
      }
    }
    // Direct { message } shape (Supabase v2 AuthError, generic Error)
    if ('message' in o && typeof o.message === 'string') return o.message;
  }
  return fallback;
}

interface RequestOptions extends Omit<RequestInit, 'body' | 'headers'> {
  body?: unknown;
  headers?: Record<string, string>;
  /** Set to true for endpoints that don't require auth (login, register). */
  skipAuth?: boolean;
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(opts.headers ?? {}),
  };

  let body: BodyInit | undefined;
  if (opts.body !== undefined) {
    if (opts.body instanceof FormData) {
      body = opts.body;
      // Let fetch set the multipart boundary automatically — do NOT set Content-Type.
    } else {
      body = JSON.stringify(opts.body);
      headers['Content-Type'] = 'application/json';
    }
  }

  if (!opts.skipAuth) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${env.apiBase}${path}`, {
    ...opts,
    headers,
    body,
  });

  const ct = res.headers.get('content-type') ?? '';
  const parseable = ct.includes('application/json');

  if (!res.ok) {
    let errBody: ApiErrorBody | null = null;
    if (parseable) {
      try {
        errBody = (await res.json()) as ApiErrorBody;
      } catch {
        // ignore
      }
    }
    throw new ApiError(res.status, errBody);
  }

  if (res.status === 204) return undefined as T;
  if (!parseable) return undefined as T;
  return (await res.json()) as T;
}
