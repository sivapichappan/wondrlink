/**
 * API request / response types.
 *
 * Source of truth: api/index.py response_data construction (~line 864).
 * When backend changes the envelope, this file must be updated in the same
 * commit. Mobile clients should never speculatively add fields; only what
 * the server actually returns.
 */

import type { ConsentField, StateChoice } from './consent-version';

// =============================================================================
// AUTH
// =============================================================================

export interface AuthRegisterRequest {
  email: string;
  password: string;
}

export interface AuthLoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token?: string;
  user: {
    id: string;
    email: string;
  };
}

// =============================================================================
// CONSENT / ACKNOWLEDGEMENT
// =============================================================================

export interface CheckAcknowledgementResponse {
  acknowledged: boolean;
  consent_version: string | null;
  current_version: string;
  needs_consent: boolean;
  state_restricted: boolean;
}

export type ConsentPayload = Record<ConsentField, boolean>;

export interface SaveAcknowledgementRequest extends ConsentPayload {
  age_confirmed: boolean;
  state: StateChoice;
}

export interface SaveAcknowledgementResponse {
  saved: boolean;
  consent_version: string;
}

export interface PrivacyAppealRequest {
  request_type: 'access' | 'deletion' | 'consent_withdrawal' | 'correction';
  description: string;
  contact_email: string;
}

// =============================================================================
// CHAT
// =============================================================================

export type ResponseLength = 'brief' | 'normal' | 'detailed';

export interface ChatRequest {
  message: string;
  response_length: ResponseLength;
  session_id: string;
}

export interface ChatSource {
  title: string;          // raw filename
  display_name: string;   // friendly name (via get_friendly_source_name)
  type: 'document';
  section: number | null; // chunk_index
  preview: string;        // first 140 chars + "..." if truncated
  is_featured?: boolean;  // true for the comprehensive guide
}

export interface ChatResource {
  title?: string;
  name?: string;
  url: string;
  type?: string;
  desc?: string;
}

export interface ChatUrgency {
  detected: boolean;
  level: string | null;
  guidance: string;
}

export interface ChatClinicalTrial {
  nct_id: string;
  title: string;
  status?: string;
  phase?: string;
  conditions?: string[];
  interventions?: string[];
  locations?: Array<{
    facility?: string;
    city?: string;
    state?: string;
    country?: string;
    distance_miles?: number;
  }>;
  relevance?: {
    score: number;
    band: 'strong' | 'moderate' | 'general';
    reasons: string[];
    warnings: string[];
  };
  url?: string;
}

export interface ChatClinicalTrialsBlock {
  found: number;
  total: number;
  trials: ChatClinicalTrial[];
  search_criteria: Record<string, unknown>;
}

/**
 * Persisted chat message as returned by /api/chat_history.
 * For assistant messages, `metadata` mirrors the bot-side fields of
 * ChatResponse so we can re-render BotResponseCard from history.
 */
export interface ChatHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  metadata?: {
    sources?: ChatSource[];
    citations?: Record<string, string>;
    followups?: string[];
    resources?: ChatResource[];
    urgency?: ChatUrgency | null;
    clinical_trials?: ChatClinicalTrialsBlock | null;
    api_used?: string;
  };
}

export interface ChatHistoryResponse {
  messages: ChatHistoryMessage[];
}

export interface SaveMessageRequest {
  role: 'user' | 'assistant';
  content: string;
  metadata?: ChatHistoryMessage['metadata'];
}

export interface ChatResponse {
  answer: string;
  api_used: 'together' | 'groq' | 'greeting-shortcircuit' | 'off-topic-filter' | string;
  retrieved_count: number;
  response_length: ResponseLength;
  patient_context_used: boolean;
  mismatch_detected: boolean;
  pii_filtered: boolean;
  validation_warnings: string[];
  medical_safety_check: boolean;
  conversation_length: number;
  has_profile_updates: boolean;
  profile_updates_saved: boolean | null;
  sources: ChatSource[];
  citations: Record<string, string>;     // "[1]" -> chunk_id
  resources: ChatResource[];
  followups: string[];                   // 3 suggested next questions
  guidelines_used: string[];
  has_guidelines: boolean;
  clinical_trials: ChatClinicalTrialsBlock | null;
  urgency: ChatUrgency | null;
  debug_info?: Record<string, unknown>;
  updated_profile_context?: Record<string, unknown>;
  profile_update_fields?: string[];
}

// =============================================================================
// HERO  (matches api/index.py:1701 /api/hero)
// =============================================================================

export interface HeroVisitSummary {
  when: string | null;
  when_pretty: string;
  pending_followups: number;
  changed_treatment: boolean;
}

export interface HeroResponse {
  has_profile: boolean;
  first_name?: string;
  phase_description?: string;
  regimen?: string;
  days_into?: number | null;
  cycle?: number | null;
  last_visit?: HeroVisitSummary | null;
  suggestions?: string[];
  error?: string;
}

// =============================================================================
// CARE SNAPSHOT  (matches api/index.py:1754 /api/care_snapshot)
// =============================================================================

export type Phq9Trend = 'improving' | 'stable' | 'worsening' | 'none';

export interface Phq9Point {
  score: number;
  completed_at: string;
}

export interface CareSnapshotResponse {
  phq9_points: Phq9Point[];
  days_since_symptom: number | null;
  phq9_trend: Phq9Trend;
  phq9_count: number;
}

// =============================================================================
// PROFILE
// =============================================================================

/**
 * The patient profile is freeform JSON server-side. Mobile treats it as an
 * opaque record + a couple of well-known top-level fields it can render.
 */
export type PatientProfile = Record<string, unknown> & {
  patient?: { firstName?: string; name?: string; age?: number; sex?: string };
  treatments?: unknown[];
  biomarkers?: unknown[];
  surgicalHistory?: unknown[];
  visit_recaps?: unknown[];
};

export interface GetPatientResponse {
  profile?: PatientProfile;
  patient_summary?: string;
  context?: Record<string, unknown>;
}

export interface UploadProfileResponse {
  status: 'ok';
  profile: PatientProfile;
  patient_summary: string;
  context: Record<string, unknown>;
}

// =============================================================================
// SCREENING
// =============================================================================

export type ScreeningInstrument = 'PHQ9' | 'GAD7' | 'PSS10' | 'ISI' | 'PREMM5';

export interface ScreeningSaveRequest {
  instrument: ScreeningInstrument;
  answers: number[];   // 0-3 per item for PHQ-9
  score: number;
}

export interface ScreeningSaveResponse {
  saved: boolean;
  is_crisis?: boolean;           // PHQ-9 Q9 >= 1
  crisis_resources?: {
    title: string;
    message: string;
    helplines: Array<{ name: string; number: string; text?: string }>;
  };
}

// =============================================================================
// CLINICAL TRIALS (standalone search, separate from chat-embedded results)
// =============================================================================

export interface ClinicalTrialsQuery {
  zip_code: string;
  stage?: string;
  radius_miles?: number;
}

export interface ClinicalTrialsResponse {
  trials: ChatClinicalTrial[];
  total: number;
  search_criteria: Record<string, unknown>;
}

// =============================================================================
// GENERIC
// =============================================================================

export interface ApiErrorBody {
  error: string;
  details?: string;
  debug_info?: Record<string, unknown>;
}
