/**
 * Defense-in-depth crisis keyword list.
 *
 * Backend already does emergency detection (lib/llm_utils.py:475) and PHQ-9 Q9
 * crisis routing (api/index.py:1004). This client-side scan intercepts BEFORE
 * the message hits the API — App Store reviewers explicitly look for this on
 * health-adjacent apps.
 *
 * Two categories:
 *   - self_harm: routes to 988 prominently
 *   - medical_emergency: routes to 911 prominently
 *
 * Updating the list does not require an app release if served from /api at
 * some point — for v1, it ships in-bundle.
 */

export type CrisisCategory = 'self_harm' | 'medical_emergency';

interface KeywordRule {
  /** Lowercased pattern matched against lowercased + space-padded input. */
  pattern: string;
  category: CrisisCategory;
}

export const CRISIS_KEYWORDS: KeywordRule[] = [
  // --- self-harm / suicide ---
  { pattern: 'suicide', category: 'self_harm' },
  { pattern: 'kill myself', category: 'self_harm' },
  { pattern: 'end my life', category: 'self_harm' },
  { pattern: 'end it all', category: 'self_harm' },
  { pattern: 'hurt myself', category: 'self_harm' },
  { pattern: 'cut myself', category: 'self_harm' },
  { pattern: 'overdose', category: 'self_harm' },
  { pattern: 'took too many', category: 'self_harm' },
  { pattern: 'no reason to live', category: 'self_harm' },
  { pattern: 'better off dead', category: 'self_harm' },
  { pattern: 'want to die', category: 'self_harm' },

  // --- cardiac / respiratory emergency ---
  { pattern: 'chest pain', category: 'medical_emergency' },
  { pattern: "can't breathe", category: 'medical_emergency' },
  { pattern: 'cant breathe', category: 'medical_emergency' },
  { pattern: 'trouble breathing', category: 'medical_emergency' },
  { pattern: 'short of breath', category: 'medical_emergency' },

  // --- hemorrhage ---
  { pattern: 'severe bleeding', category: 'medical_emergency' },
  { pattern: 'vomiting blood', category: 'medical_emergency' },
  { pattern: 'coughing up blood', category: 'medical_emergency' },
  { pattern: "can't stop bleeding", category: 'medical_emergency' },
  { pattern: 'cant stop bleeding', category: 'medical_emergency' },

  // --- stroke ---
  { pattern: 'slurred speech', category: 'medical_emergency' },
  { pattern: 'numb on one side', category: 'medical_emergency' },
  { pattern: 'face drooping', category: 'medical_emergency' },

  // --- fever-during-chemo (already detected server-side, but redundancy is OK) ---
  { pattern: 'high fever', category: 'medical_emergency' },
];

export interface GuardrailHit {
  matched: string;
  category: CrisisCategory;
}

/**
 * Run the message against the keyword rules. Returns the first match or null.
 * The check is case-insensitive and surrounded by spaces so partial-word hits
 * like "killer" don't trigger.
 */
export function scanForCrisis(message: string): GuardrailHit | null {
  if (!message) return null;
  const padded = ` ${message.toLowerCase().replace(/\s+/g, ' ')} `;
  for (const rule of CRISIS_KEYWORDS) {
    const needle = ` ${rule.pattern.toLowerCase()} `;
    // also allow needle followed by punctuation
    if (padded.includes(needle)) {
      return { matched: rule.pattern, category: rule.category };
    }
    if (padded.includes(` ${rule.pattern.toLowerCase()}.`)) {
      return { matched: rule.pattern, category: rule.category };
    }
    if (padded.includes(` ${rule.pattern.toLowerCase()},`)) {
      return { matched: rule.pattern, category: rule.category };
    }
  }
  return null;
}
