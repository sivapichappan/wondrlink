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
export type CardKind =
  | 'anchor_cancer'
  | 'scan_suggestion'
  | 'trials_ask'
  | 'check_in'
  | 'name_ask';
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

/** A check-in question, as the engine chose it (redesign change 4). */
export interface CheckInQuestion {
  id: string;
  topic: string;
  text: string;
  chips: string[];
}

export interface CheckInDue {
  due: boolean;
  questions: CheckInQuestion[];
}

/** What Sage would ask right now, or due: false. Never throws. */
export async function fetchCheckIn(): Promise<CheckInDue> {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) return { due: false, questions: [] };
    const res = await fetch(`${env.apiBase}/api/checkin/due`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return { due: false, questions: [] };
    const body = await res.json();
    return { due: !!body?.due, questions: body?.questions ?? [] };
  } catch {
    return { due: false, questions: [] };
  }
}

/**
 * Put the offered questions on cooldown. Fire-and-forget: a lost record
 * means the check-in is offered again, which is recoverable; a thrown error
 * mid-conversation is not.
 */
export async function recordCheckIn(
  questionIds: string[],
  outcome: 'answered' | 'declined',
): Promise<void> {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) return;
    await fetch(`${env.apiBase}/api/checkin/record`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ question_ids: questionIds, outcome }),
    }).catch(() => {});
  } catch {
    // Swallow everything.
  }
}
