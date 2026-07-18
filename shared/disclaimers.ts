/**
 * Canonical disclaimer / helpline copy.
 *
 * These strings must appear VERBATIM wherever they're shown. Attorney-reviewed
 * copy is non-negotiable; do not paraphrase in the UI.
 *
 * Web counterparts live in public/index.html (banner + welcome + per-message
 * footer). State-restricted copy mirrors lib/compliance.py validate_state().
 * Crisis helplines mirror api/index.py crisis short-circuit + lib/llm_utils.py
 * cancer-helpline list. Search by constant name in those files to find them.
 */

// =============================================================================
// PERSISTENT BANNERS
// =============================================================================

export const AI_DISCLOSURE_BANNER =
  "You're chatting with an AI assistant — not a person, not medical advice. AI can make mistakes; please verify important information with your care team.";

export const WELCOME_INTRO =
  "I'm here to help you understand your diagnosis and treatment options in simple, everyday language. This is a support tool, not medical advice.";

/** Cancer-aware variant used inside the chat empty state. Pass the lower-cased
 *  display name (e.g. "lung cancer") or omit for a generic welcome. */
export function welcomeIntroFor(cancerDisplay?: string | null): string {
  if (!cancerDisplay) return WELCOME_INTRO;
  const lc = cancerDisplay.toLowerCase();
  return `I'm here to help you understand your ${lc} diagnosis and treatment options in simple, everyday language. This is a support tool, not medical advice.`;
}

export const PER_MESSAGE_FOOTER =
  'Informational only. Verify with your oncologist.';

// =============================================================================
// CONSENT SCREEN
// =============================================================================

export const CONSENT_LABELS = {
  age_confirmed: 'I confirm I am 18 years of age or older.',
  consent_collection:
    'I consent to WondrLink collecting my health-related information for the purpose of providing personalized educational responses.',
  consent_sharing:
    'I consent to WondrLink sending my de-identified queries to its AI providers (Together AI, Groq) for response generation.',
  consent_terms:
    'I have reviewed the Consumer Health Data Privacy Notice, the Privacy Policy, and the Terms of Use, and I accept them.',
} as const;

export const CONSENT_INTRO =
  'Before you start, please confirm a few things. Each consent below is independent — please check only those you agree to.';

// =============================================================================
// STATE RESTRICTED
// =============================================================================

export const STATE_BLOCKED_TITLE = "WondrLink isn't available in your state yet";

export const STATE_BLOCKED_MESSAGE =
  'WondrLink is not currently available to residents of Illinois or Nevada due to state regulations governing AI in mental and behavioral health. We are actively working to expand access — thank you for your patience.';

// =============================================================================
// HELPLINES — Cancer support (informational, non-crisis)
// =============================================================================

export interface Helpline {
  name: string;
  number: string;            // e.g. "1-800-227-2345" — used as label
  tel: string;               // tel:URI for Linking.openURL
  desc: string;
  textTo?: string;           // optional text-to number for SMS-supporting lines
}

export const CANCER_HELPLINES: Helpline[] = [
  {
    name: 'American Cancer Society',
    number: '1-800-227-2345',
    tel: 'tel:18002272345',
    desc: '24/7 cancer information and support',
  },
  {
    name: 'CCA Helpline',
    number: '1-877-422-2030',
    tel: 'tel:18774222030',
    desc: 'M–F 9am–9pm ET — colorectal-specific support',
  },
  {
    name: 'NCI Cancer Info Service',
    number: '1-800-422-6237',
    tel: 'tel:18004226237',
    desc: 'M–F 9am–9pm ET — National Cancer Institute',
  },
  {
    name: 'Cancer Support Helpline',
    number: '1-888-793-9355',
    tel: 'tel:18887939355',
    desc: 'Free, confidential counseling',
  },
];

// =============================================================================
// HELPLINES — Crisis (life-threatening, mental health)
// =============================================================================

export const CRISIS_HELPLINES: Helpline[] = [
  {
    name: 'Emergency',
    number: '911',
    tel: 'tel:911',
    desc: 'Medical emergencies, severe symptoms, immediate danger',
  },
  {
    name: 'Suicide & Crisis Lifeline',
    number: '988',
    tel: 'tel:988',
    desc: 'Free, 24/7 — call or text',
    textTo: 'sms:988',
  },
  {
    name: 'Crisis Text Line',
    number: 'Text HOME to 741741',
    tel: 'sms:741741&body=HOME',
    desc: 'Free, 24/7 text-based crisis counseling',
  },
];

// =============================================================================
// CONTACT
// =============================================================================

export const CONTACT = {
  privacy: 'privacy@wondrlinkfoundation.org',
  appeals: 'appeals@wondrlinkfoundation.org',
  security: 'security@wondrlinkfoundation.org',
  website: 'https://www.wondrlinkfoundation.org',
} as const;

// =============================================================================
// CRISIS MODAL (shown when client-side guardrail intercepts a message)
// =============================================================================

export const CRISIS_MODAL = {
  title: 'It sounds like you may need urgent help',
  body:
    'Sage is not equipped to help in an emergency. If you are in danger or in crisis, please reach out to one of the resources below now.',
  continueButton: 'I understand — continue anyway',
} as const;
