/**
 * Modeler trigger — fire-and-forget end-of-conversation ping (Push 2).
 *
 * Deliberately NOT using apiFetch: this call must never surface an error,
 * never block UI, and never retry. The server's debounce gates do the real
 * limiting (≥3 new events, ≥1h interval, ≤2/day); the endpoint 403s while
 * FEATURE_MODELER is off and that is fine — the nightly cron makes the system
 * whole without any client help.
 */

import { env } from '../env';
import { supabase } from '../supabase';

export async function pingModeler(): Promise<void> {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) return;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    await fetch(`${env.apiBase}/api/modeler/run`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    }).catch(() => {});
    clearTimeout(timer);
  } catch {
    // Swallow everything — the cron is the safety net.
  }
}
