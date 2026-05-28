/**
 * Care + Profile API wrappers.
 */

import { ENDPOINTS } from '@shared/api-contracts';
import type {
  CancerOptionsResponse,
  CareSnapshotResponse,
  GetPatientResponse,
  HeroResponse,
  PatientProfile,
  PatientRole,
  UpdateCancerSlugResponse,
  UploadProfileResponse,
} from '@shared/types';

import { apiFetch } from './client';

export function fetchHero() {
  return apiFetch<HeroResponse>(ENDPOINTS.hero, { method: 'GET' });
}

export function fetchCareSnapshot() {
  return apiFetch<CareSnapshotResponse>(ENDPOINTS.careSnapshot, { method: 'GET' });
}

export function fetchProfile() {
  return apiFetch<GetPatientResponse>(ENDPOINTS.getPatient, { method: 'GET' });
}

export function uploadProfile(profile: PatientProfile) {
  return apiFetch<UploadProfileResponse>(ENDPOINTS.uploadProfile, {
    method: 'POST',
    body: profile,
  });
}

export function clearProfile() {
  return apiFetch<{ status: 'ok' }>(ENDPOINTS.clearProfile, { method: 'POST' });
}

export function fetchCancerOptions(includePreview = false) {
  const qs = includePreview ? '?include_preview=1' : '';
  return apiFetch<CancerOptionsResponse>(`${ENDPOINTS.cancerOptions}${qs}`, { method: 'GET' });
}

export function updateCancerSlug(cancer_slug: string, role: PatientRole = 'patient') {
  return apiFetch<UpdateCancerSlugResponse>(ENDPOINTS.updateCancerSlug, {
    method: 'POST',
    body: { cancer_slug, role },
  });
}
