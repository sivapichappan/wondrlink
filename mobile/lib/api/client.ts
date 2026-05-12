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
    super(message ?? body?.error ?? `Request failed with ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
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
