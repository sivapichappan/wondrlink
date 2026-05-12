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

  // --- Consent / Compliance ---
  checkAcknowledgement: '/api/check_acknowledgement',
  saveAcknowledgement: '/api/save_acknowledgement',
  privacyAppeal: '/api/privacy_appeal',

  // --- Chat ---
  chat: '/api/chat',
  chatHistory: '/api/chat_history',
  saveMessage: '/api/save_message',
  clearChat: '/api/clear_chat',
  feedback: '/api/feedback',

  // --- Profile ---
  uploadProfile: '/api/upload_profile',
  getPatient: '/api/get_patient',
  clearProfile: '/api/clear_profile',

  // --- Care ---
  hero: '/api/hero',
  careSnapshot: '/api/care_snapshot',

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
