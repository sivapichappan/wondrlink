/**
 * API endpoint paths.
 *
 * Mirrors api/index.py routes. Request/response shapes live in ./types.ts.
 * Mobile clients should compose `${API_BASE}${ENDPOINTS.X}` rather than
 * hardcoding strings.
 *
 * API_BASE is configured per-environment in the mobile app (app.config.ts):
 *   - development: http://localhost:5328 (or wherever Flask runs locally)
 *   - production:  https://wondrlink.foundation (or the live Vercel domain)
 */

export const ENDPOINTS = {
  // --- Auth (no auth header required) ---
  authRegister: '/api/auth/register',
  authLogin: '/api/auth/login',
  authLogout: '/api/auth/logout',
  authMe: '/api/auth/me',
  authPhoneSend: '/api/auth/phone/send',
  authPhoneVerify: '/api/auth/phone/verify',
  accountBasics: '/api/account/basics',

  // --- Consent / Compliance ---
  checkAcknowledgement: '/api/check_acknowledgement',
  saveAcknowledgement: '/api/save_acknowledgement',
  privacyAppeal: '/api/privacy_appeal',
  consentStatus: '/api/consent_status',
  withdrawConsent: '/api/withdraw_consent',
  limitSensitivePi: '/api/limit_sensitive_pi',

  // --- Chat ---
  chat: '/api/chat',
  chatHistory: '/api/chat_history',
  saveMessage: '/api/save_message',
  clearChat: '/api/clear_chat',
  feedback: '/api/feedback',

  // --- Safety (escalation card actions) ---
  safetyLogSymptom: '/api/safety/log_symptom',

  // --- Glossary (personal term dictionary) ---
  glossaryExplain: '/api/glossary/explain',
  glossary: '/api/glossary',
  glossaryTerm: (id: string) => `/api/glossary/${id}`,

  // --- Report scan (on-device OCR -> de-identified extraction -> confirm) ---
  reportExtract: '/api/report/extract',
  reportApply: '/api/report/apply',

  // --- Conversations (multi-conversation drawer: New chat / Recents / Search) ---
  // list (GET) + create (POST) share the base path. `conversation(id)` builds
  // the per-conversation paths: GET `${...}/messages`, PATCH rename, DELETE.
  conversations: '/api/conversations',
  conversationsSearch: '/api/conversations/search',
  conversation: (id: string) => `/api/conversations/${id}`,
  conversationMessages: (id: string) => `/api/conversations/${id}/messages`,

  // --- Patient lifecycle (belief store) ---
  confirmBelief: '/api/confirm_belief',

  // --- Connection-map review workspace (reviewer accounts only; every route
  // executes on the restricted sage_review database role server-side) ---
  reviewMeta: '/api/review/meta',
  reviewQueue: '/api/review/queue',
  reviewEdge: (id: string) => `/api/review/edge/${id}`,
  reviewAttest: (id: string) => `/api/review/edge/${id}/attest`,
  reviewVersionBlockers: (id: string) => `/api/review/version/${id}/blockers`,
  reviewVersionPublish: (id: string) => `/api/review/version/${id}/publish`,
  reviewConcept: '/api/review/concept',
  // Admin only. Approving is not an UPDATE server-side: sage_review holds
  // SELECT on reviewer by design, so the decision goes through a SECURITY
  // DEFINER function that also creates the sandbox and writes audit_log.
  reviewApplications: '/api/review/applications',
  reviewApplicationDecide: (id: string) => `/api/review/applications/${id}/decide`,

  // --- Becoming a reviewer (patient-app routes: an applicant is not a
  // reviewer yet, so these cannot sit behind the review blueprint) ---
  reviewerApply: '/api/reviewer/apply',

  // --- Reviewer sandbox (§5.5): the chat a reviewer tests on, backed by a
  // SYNTHETIC patient in separate tables. A reviewer may not hold a patient
  // profile, so there is no patient chat route they could use instead. ---
  sandboxChat: '/api/sandbox/chat',
  sandboxConversations: '/api/sandbox/conversations',
  sandboxConversationMessages: (id: string) => `/api/sandbox/conversations/${id}/messages`,
  sandboxReset: '/api/sandbox/reset',

  // --- Push notifications. A token is a persistent device identifier, so it
  // is user data: delete_all_user_data() clears device_push_token. ---
  // Pulls the guideline corpus into the serving container ahead of a question,
  // so the first message does not wait ~9s for a corpus that never changes.
  warm: '/api/warm',

  // --- Recovering a question the app was backgrounded out of ---
  // Poll target: one indexed row, and it carries the conversation id that a
  // brand-new thread never learned because the response died with the socket.
  chatTurnStatus: (clientTurnId: string) => `/api/chat/turn/${clientTurnId}`,
  // "Tell me when this lands." Fired from AppState 'background', so it has to
  // return fast: iOS gives a few seconds before it suspends everything.
  chatNotifyWhenReady: '/api/chat/notify_when_ready',

  pushRegister: '/api/push/register',
  pushUnregister: '/api/push/unregister',

  // --- Profile (clearProfile is POST per api/index.py:307) ---
  uploadProfile: '/api/upload_profile',
  getPatient: '/api/get_patient',
  clearProfile: '/api/clear_profile',

  // --- Care ---
  hero: '/api/hero',
  careSnapshot: '/api/care_snapshot',

  // --- Cancer registry (multi-cancer switcher) ---
  cancerOptions: '/api/cancer_options',
  updateCancerSlug: '/api/update_cancer_slug',

  // --- Screening (PHQ-9 etc.) ---
  screeningSave: '/api/screening/save',
  screeningLoad: '/api/screening/load',
  screeningHistory: '/api/screening/history',

  // --- Tools ---
  surveillance: '/api/surveillance',
  previsitQuestions: '/api/previsit_questions',
  visitRecap: '/api/visit_recap',
  clinicalTrials: '/api/clinical_trials',
  deepResearch: '/api/deep_research',
  insuranceAppeal: '/api/insurance_appeal',

  // --- Account ---
  deleteAccount: '/api/delete_account',

  // --- Public ---
  dataSources: '/api/data_sources',
  health: '/api/health',
} as const;

export type EndpointKey = keyof typeof ENDPOINTS;
