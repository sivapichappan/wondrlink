/**
 * Trial-interaction feedback — fire-and-forget telemetry (Push 3).
 *
 * Mirrors lib/api/modeler.ts: deliberately NOT apiFetch. Saves/removes must
 * never surface an error or block the watchlist UI; the event lands in
 * patient_events server-side and feeds the Modeler's timeline.
 */

import { env } from '../env';
import { supabase } from '../supabase';

export type TrialFeedbackAction = 'saved' | 'removed' | 'viewed';

export async function sendTrialFeedback(
  nctId: string,
  action: TrialFeedbackAction,
  surface: 'tools' | 'chat' | 'watchlist' = 'tools',
): Promise<void> {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) return;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    await fetch(`${env.apiBase}/api/trials/feedback`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ nct_id: nctId, action, surface }),
      signal: controller.signal,
    }).catch(() => {});
    clearTimeout(timer);
  } catch {
    // Swallow everything — telemetry must never break the UI.
  }
}
