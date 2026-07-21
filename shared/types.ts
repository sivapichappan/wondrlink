/**
 * API request / response types.
 *
 * Source of truth: api/index.py — specifically the chat response_data
 * construction inside api_chat(). When the backend changes the envelope,
 * this file must be updated in the same commit. Mobile clients should never
 * speculatively add fields; only what the server actually returns.
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
  cancer_slug?: string | null;
  cancer_display?: string | null;
  needs_cancer_pick?: boolean;
  /** Sage onboarding: who-for + basics screens still needed (absent on older servers). */
  needs_basics?: boolean;
  perspective?: 'self' | 'caregiver';
  account_holder_name?: string | null;
}

/** Sage onboarding basics (screens 2/2a/2b). */
export interface AccountBasicsRequest {
  perspective: 'self' | 'caregiver';
  account_holder_name: string;
  /** Required when perspective is caregiver. */
  patient_name?: string;
  relationship?: string;
  birth_year?: number;
  gender?: 'Female' | 'Male' | 'Other';
  location?: { lat?: number; lng?: number; display: string };
}

export type ConsentPayload = Record<ConsentField, boolean>;

export type AgeBand = '18-24' | '25-34' | '35-44' | '45-54' | '55-64' | '65-74' | '75+';

export interface SaveAcknowledgementRequest extends ConsentPayload {
  // Server prefers `date_of_birth` (re-validated server-side; raw DOB is
  // never persisted — we keep only the derived `age_band` + `is_adult`
  // in consent_metadata). `age_confirmed` is kept for back-compat with
  // the legacy single-checkbox path.
  date_of_birth?: string; // "YYYY-MM-DD"
  age_band?: AgeBand;
  age_confirmed?: boolean;
  state: StateChoice;
  cancer_slug?: string;
  role?: 'patient' | 'caregiver';
}

export interface SaveAcknowledgementResponse {
  saved: boolean;
  consent_version: string;
}

// Returned by /api/consent_status (GET) — per-key grant state + a
// composite chat_disabled flag (true iff collection OR sharing is
// withdrawn). Used by the Consent Management screen and the chat
// gating banner.
export interface ConsentStatusResponse {
  consent_collection: { granted: boolean; changed_at: string | null };
  consent_sharing:    { granted: boolean; changed_at: string | null };
  consent_terms:      { granted: boolean; changed_at: string | null };
  chat_disabled: boolean;
}

export interface WithdrawConsentRequest {
  consent_key: ConsentField;
  action: 'withdraw' | 'restore';
  reason?: string;
}

export interface WithdrawConsentResponse {
  status: 'ok';
  consent_status: ConsentStatusResponse;
}

// CCPA/CPRA "Limit Use of Sensitive Personal Information" affordance.
// Operationally a no-op (we don't use SPI for advertising or sale) —
// the endpoint persists the preference timestamp for auditability.
export interface LimitSpiResponse {
  limited: boolean;
  confirmed_at: string | null;
}

export type PrivacyAppealType = 'access' | 'deletion' | 'consent_withdrawal' | 'other';

export interface PrivacyAppealRequest {
  request_type: PrivacyAppealType;
  reason: string;
}

export interface PrivacyAppealResponse {
  status: 'ok';
  appeal_id: string;
  sla_due: string;
  message: string;
}

export interface FeedbackRequest {
  rating: 'up' | 'down';
  message_preview?: string;
}

// =============================================================================
// CHAT
// =============================================================================

export type ResponseLength = 'brief' | 'normal' | 'detailed';

export interface ChatRequest {
  message: string;
  response_length: ResponseLength;
  session_id: string;
  /**
   * Target conversation for the multi-conversation model. A real conversation
   * UUID appends to that thread; "new" (or null) starts a fresh one; omitting
   * the field entirely is the legacy single-thread behavior. See ChatResponse
   * for the id/title the server assigns.
   */
  conversation_id?: string | 'new' | null;
}

/** A named chat conversation (drawer Recents / Search). */
export interface Conversation {
  id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
}

export interface ConversationsListResponse {
  conversations: Conversation[];
}

/** A fact awaiting the user's "is that right?" confirmation (belief store). */
export interface PendingConfirmation {
  id: string;
  path: string;
  prompt: string;
  proposed_value?: unknown;
}

/** Passive-lifecycle stage (see lib/question_policy.py — monotonic ladder). */
export type LifecycleStage =
  | 'getting_to_know_you'
  | 'understanding_treatment'
  | 'connected'
  | 'trial_ready';

export interface CreateConversationResponse {
  id: string;
  title: string;
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

export type TrialRadius = 25 | 50 | 100 | 'nationwide';

export interface ChatClinicalTrial {
  nct_id: string;
  title: string;
  official_title?: string;
  status?: string;
  raw_status?: string;
  phase?: string;
  conditions?: string[];
  interventions?: Array<{ name: string; type?: string }>;
  study_type?: string;
  study_purpose?: string;
  plain_summary?: string;
  brief_summary?: string;
  enrollment_count?: number;
  eligibility?: {
    min_age?: string;
    max_age?: string;
    sex?: string;
    healthy_volunteers?: string;
  };
  central_contact?: { name?: string; phone?: string; email?: string };
  locations?: Array<{
    facility?: string;
    city?: string;
    state?: string;
    zip?: string;
    country?: string;
    status?: string;
    distance_miles?: number;
    lat?: number;
    lon?: number;
  }>;
  nearest_distance_miles?: number;
  relevance?: {
    score: number;
    band: 'strong' | 'moderate' | 'general';
    reasons: string[];
    warnings: string[];
    /** Present when the patient's connections graph adjusted this trial (Push 3). */
    graph?: { applied: boolean; delta: number; edge_ids: string[] };
  };
  // Flat mirrors the web SPA reads (kept alongside nested `relevance`).
  relevance_score?: number;
  relevance_reasons?: string[];
  relevance_warnings?: string[];
  likely_eligible?: boolean;
  url?: string;
}

export interface ChatClinicalTrialsBlock {
  found: number;
  total: number;
  trials: ChatClinicalTrial[];
  search_criteria: Record<string, unknown>;
}

// =============================================================================
// SAFETY CLASSIFIER  (pre-chat tiering; config/safety/ rules)
// =============================================================================

export type SafetyTier = 'T1' | 'T2' | 'T3' | 'MH';

/**
 * Escalation payload from the pre-chat safety classifier.
 * T1/T2/MH arrive on a short-circuit response (no normal answer — the
 * `answer` field is the crisis response text and the card renders above
 * it). T3 arrives alongside a normal answer as a same-day banner.
 */
export interface ChatSafety {
  tier: SafetyTier;
  category: string;
  patient_line: string;
  rule_matched: boolean;
  confidence?: number;
  /** Config value (911 default) so non-US launches are an env change. */
  emergency_number: string;
  /** T2 only: show the "Log this symptom" action. */
  offer_symptom_log?: boolean;
  rules_version?: string;
}

/** Structured crisis resources (mirrors the PHQ-9 screening path's shape). */
export interface CrisisResources {
  message: string;
  resources: { name: string; contact: string }[];
}

export interface LogSymptomRequest {
  tier: SafetyTier;
  category: string;
  note?: string;
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
    pending_confirmations?: PendingConfirmation[] | null;
    api_used?: string;
    is_crisis?: boolean;
    crisis_resources?: CrisisResources | null;
    crisis_category?: string | null;
    safety?: ChatSafety | null;
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
  /** Set on safety-classifier escalations (T1/T2/MH short-circuit, or T3
   *  banner alongside a normal answer). */
  is_crisis?: boolean;
  crisis_resources?: CrisisResources | null;
  crisis_category?: string | null;
  safety?: ChatSafety | null;
  /** Facts awaiting "is that right?" confirmation (belief store). */
  pending_confirmations?: PendingConfirmation[] | null;
  /** The patient's lifecycle stage after this turn. */
  lifecycle_stage?: LifecycleStage | null;
  /** Conversation this turn was persisted to (multi-conversation model). */
  conversation_id?: string | null;
  /** Server-assigned title, echoed on the first turn of a new conversation. */
  title?: string | null;
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
  cancer_slug?: string | null;
  cancer_display?: string | null;
  error?: string;
}

// =============================================================================
// CANCER REGISTRY  (matches api/index.py /api/cancer_options + /api/update_cancer_slug)
// =============================================================================

export interface CancerOption {
  slug: string;
  display_name: string;
  short_name: string;
  ready: boolean;
  accent_color: string;
  icon: string;
  doc_count: number;
  chunk_count: number;
}

export interface CancerOptionsResponse {
  options: CancerOption[];
}

export type PatientRole = 'patient' | 'caregiver';

export interface UpdateCancerSlugRequest {
  cancer_slug: string;
  role?: PatientRole;
}

export interface UpdateCancerSlugResponse {
  status: 'ok';
  cancer_slug: string;
  cancer_display: string;
  role: PatientRole;
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
  /** Passive-lifecycle stage (absent on older servers). */
  lifecycle_stage?: LifecycleStage;
  /** "What WondrChat knows" summary for My Care (absent on older servers). */
  coverage?: {
    score: number;
    known_count: number;
    missing_top: string[];
  } | null;
}

export interface UploadProfileResponse {
  status: 'ok';
  profile: PatientProfile;
  patient_summary: string;
  context: Record<string, unknown>;
}

// =============================================================================
// SCREENING  (matches api/index.py:984 /api/screening/save)
// =============================================================================

export type ScreeningInstrument = 'PHQ9' | 'GAD7' | 'PSS10' | 'ISI' | 'PREMM5' | 'SYMPTOM';

export interface ScreeningSaveRequest {
  instrument: ScreeningInstrument;
  scores: Record<string, number>;   // e.g. { q1: 2, q2: 1, ... }
  total_score: number;
  severity_label?: string;
}

export interface ScreeningCrisisResources {
  message: string;
  resources: Array<{ name: string; contact: string }>;
}

export interface ScreeningSaveResponse {
  status: 'ok' | 'error';
  is_crisis: boolean;
  crisis_resources: ScreeningCrisisResources | null;
  total_score: number;
  severity_label?: string;
}

// =============================================================================
// SURVEILLANCE  (matches api/index.py:1069 /api/surveillance)
// =============================================================================

export interface SurveillanceMilestone {
  test: string;
  when: string;
  due_date?: string | null;
  rationale?: string;
}

export interface SurveillanceResponse {
  status: 'ok';
  schedule?: SurveillanceMilestone[] | null;
  message?: string;
  stage?: string;
  surgery_date?: string;
}

// =============================================================================
// PRE-VISIT QUESTIONS  (matches api/index.py:1170 /api/previsit_questions)
// =============================================================================

export interface PreVisitGroup {
  topic: string;
  questions: string[];
}

export interface PreVisitRequest {
  context?: string;
}

export interface PreVisitResponse {
  status: 'ok' | 'feature_disabled';
  groups: PreVisitGroup[];
  used_fallback: boolean;
  cached: boolean;
  saved: boolean;
}

// =============================================================================
// VISIT RECAP  (matches api/index.py:1247 /api/visit_recap)
// =============================================================================

export interface VisitRecapStructured {
  discussed: string[];
  treatment_changes: string[];
  action_items: string[];
  follow_up_questions: string[];
  flags: string[];
  used_fallback: boolean;
}

export interface VisitRecapRequest {
  transcript: string;
}

/** A persisted visit recap stored in profile.visit_recaps (api/index.py api_visit_recap). */
export interface VisitRecapEntry {
  timestamp: string;
  transcript_preview: string;
  recap: {
    discussed: string[];
    treatment_changes: string[];
    action_items: string[];
    follow_up_questions: string[];
    flags: string[];
  };
  used_fallback?: boolean;
}

export interface VisitRecapResponse {
  status: 'ok' | 'feature_disabled';
  recap: VisitRecapStructured;
  saved: boolean;
  truncated: boolean;
}

// =============================================================================
// INSURANCE APPEAL  (matches api/index.py:1327 /api/insurance_appeal)
// =============================================================================

export interface InsuranceAppealResponse {
  status: 'ok' | 'feature_disabled' | 'error';
  draft: string;
  citations: Record<string, string>;
  sources: Array<{ title: string; section: number | null; preview: string }>;
  saved: boolean;
}

// =============================================================================
// DEEP RESEARCH  (matches api/index.py:1478 /api/deep_research)
// =============================================================================

export interface DeepResearchSection {
  title: string;
  body: string;
}

export interface DeepResearchResponse {
  status: 'ok' | 'off_topic' | 'feature_disabled';
  report: string;
  sections: DeepResearchSection[];
  citations: Record<string, string>;
  sources: Array<{ title: string; section: number | null; preview: string }>;
  verified: boolean;
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
  status?: 'ok' | 'error';
  trials: ChatClinicalTrial[];
  total_found?: number;
  radius_miles?: number | null;
  relaxed_location?: boolean;
  // Per-radius total recruiting counts, e.g. { "25": 52, "100": 186, "nationwide": 438 }
  radius_counts?: Record<string, number | null> | null;
  search_criteria?: Record<string, unknown>;
  error?: string;
  missing_critical?: string[];
  missing_helpful?: string[];
}

// =============================================================================
// GENERIC
// =============================================================================

export interface ApiErrorBody {
  error: string;
  details?: string;
  debug_info?: Record<string, unknown>;
}
