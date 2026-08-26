/**
 * Dealt-card engagement telemetry (redesign change 3).
 *
 * Cards are the only way anything reaches a patient once the tool grid is
 * gone, so the brief makes measuring them a build requirement: "if cards
 * underperform, scanning starves, the model stays ignorant, and trials never
 * unlock." This is how we would ever know.
 *
 * Deliberately NOT apiFetch, same reasoning as the Modeler ping: instrumenting
 * a surface must never be able to break it. No errors surface, no retries, no
 * blocking. A dropped event is a lost data point, never a broken card.
 */

import { env } from '../env';
import { supabase } from '../supabase';

/** Must match CARD_KINDS in api/index.py. */
export type CardKind = 'anchor_cancer' | 'scan_suggestion' | 'trials_ask';
export type CardAction = 'shown' | 'acted' | 'dismissed';

export async function logCardEvent(card: CardKind, action: CardAction): Promise<void> {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) return;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    await fetch(`${env.apiBase}/api/events/card`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ card, action }),
      signal: controller.signal,
    }).catch(() => {});
    clearTimeout(timer);
  } catch {
    // Swallow everything.
  }
}
