/**
 * Care-tool API wrappers.
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  ChatClinicalTrialsBlock,
  ClinicalTrialsResponse,
  DeepResearchResponse,
  InsuranceAppealResponse,
  PreVisitRequest,
  PreVisitResponse,
  ScreeningSaveRequest,
  ScreeningSaveResponse,
  SurveillanceResponse,
  TrialRadius,
  VisitRecapRequest,
  VisitRecapResponse,
} from '@shared/types';

import { apiFetch } from './client';

export function saveScreening(body: ScreeningSaveRequest) {
  return apiFetch<ScreeningSaveResponse>(ENDPOINTS.screeningSave, {
    method: 'POST',
    body,
  });
}

export interface ScreeningHistoryPoint {
  total_score: number;
  severity_label?: string;
  created_at: string;
}

export interface ScreeningHistoryResponse {
  status: 'ok';
  history: Record<string, ScreeningHistoryPoint[]>;
}

export function fetchScreeningHistory() {
  return apiFetch<ScreeningHistoryResponse>(ENDPOINTS.screeningHistory, { method: 'GET' });
}

export function fetchSurveillance() {
  return apiFetch<SurveillanceResponse>(ENDPOINTS.surveillance, { method: 'GET' });
}

export function fetchClinicalTrials(
  limit = 5,
  radius: TrialRadius = 100,
  opts: { counts?: boolean } = {},
) {
  const countsParam = opts.counts ? '&counts=1' : '';
  return apiFetch<ClinicalTrialsResponse>(
    `${ENDPOINTS.clinicalTrials}?limit=${limit}&radius=${radius}${countsParam}`,
    { method: 'GET' },
  );
}

export function generatePreVisitQuestions(body: PreVisitRequest = {}) {
  return apiFetch<PreVisitResponse>(ENDPOINTS.previsitQuestions, {
    method: 'POST',
    body,
  });
}

export function generateVisitRecap(body: VisitRecapRequest) {
  return apiFetch<VisitRecapResponse>(ENDPOINTS.visitRecap, {
    method: 'POST',
    body,
  });
}

export function deepResearch(query: string) {
  return apiFetch<DeepResearchResponse>(ENDPOINTS.deepResearch, {
    method: 'POST',
    body: { query },
  });
}

interface AppealUploadOptions {
  denialText?: string;
  pdf?: { uri: string; name: string; mimeType?: string };
}

export function submitInsuranceAppeal(opts: AppealUploadOptions) {
  const form = new FormData();
  if (opts.denialText) form.append('denial_text', opts.denialText);
  if (opts.pdf) {
    form.append('denial_pdf', {
      uri: opts.pdf.uri,
      name: opts.pdf.name,
      type: opts.pdf.mimeType || 'application/pdf',
    } as unknown as Blob);
  }
  return apiFetch<InsuranceAppealResponse>(ENDPOINTS.insuranceAppeal, {
    method: 'POST',
    body: form,
  });
}
