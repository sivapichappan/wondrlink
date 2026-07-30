/**
 * Connection-map review workspace API (reviewer accounts only).
 *
 * Every one of these routes runs on the restricted sage_review database role
 * server-side: a reviewer session provably cannot reach patient data, and the
 * server answers a uniform 403 for anyone who is not an active reviewer.
 *
 * Shapes mirror lib/connection_map/review/api.py responses.
 */

import { ENDPOINTS } from '@shared/api-contracts';

import { apiFetch } from './client';

export interface ReviewConceptRef {
  slug: string | null;
  display: string | null;
  display_patient: string | null;
}

export interface ReviewEvidence {
  quoted_sentence: string;
  section_ref: string;
  document_title: string | null;
  publisher: string | null;
  /** 'cancer_specific' | 'general_survivorship' — §5.4 labels every quote. */
  scope: string | null;
}

export interface ReviewQueueItem {
  id: string;
  relationship: string;
  tier: 'A' | 'B' | 'C';
  urgency: 'routine' | 'urgent';
  status: 'candidate' | 'in_review' | 'approved' | 'rejected';
  origin: string;
  src: ReviewConceptRef;
  dst: ReviewConceptRef;
  patient_phrasing: string | null;
  expected_prevalence_low: number | null;
  expected_prevalence_high: number | null;
  evidence: ReviewEvidence[];
  /** Why a chained (tier B) candidate's quotations combine. The model's own
   * argument, not a claim any source makes — the UI labels it as such. Null on a
   * candidate that rests on a single quotation. */
  chain_reasoning: string | null;
  /** Fingerprint of this connection as it is being shown. It goes back with the
   * signature so the server can refuse if the connection changed in between —
   * otherwise a citation added while the card was open would land inside a
   * signature nobody read. */
  edge_hash: string;
  /** The exact wording a signature endorses; null = no approved wording for
   * this tier yet (tier C until the attorney variant lands) — signing is
   * refused server-side. */
  attestation: { version: string; text: string } | null;
}

export interface ReviewQueueResponse {
  status: 'ok';
  items: ReviewQueueItem[];
  /** How many came back in this page. */
  count: number;
  /** How many exist. Differs from `count` only if a page fills, and the progress
   *  indicator needs the one that cannot understate the work left. */
  total: number;
}

export interface ReviewMetaResponse {
  status: 'ok';
  reviewer: { name: string | null; role: string };
  relationship_types: string[];
}

export interface ReviewEditResponse {
  status: 'ok';
  /** D1 soft notes — advisory, the physician decides. */
  concerns?: string[];
}

export interface ReviewAttestResponse {
  status: 'ok';
  attestation_id: string;
  decision: 'approve' | 'reject';
}

/** §13.1 — the structured rejection vocabulary, mirrored from the DB CHECK. */
export const REJECTION_REASONS = [
  'quote_does_not_support',
  'quote_out_of_context',
  'too_general',
  'wrong_relationship_type',
  'not_appropriate_for_patients',
  'clinically_incorrect',
  'duplicate',
  'chain_does_not_hold',
] as const;
export type RejectionReason = (typeof REJECTION_REASONS)[number];

export const REJECTION_REASON_LABELS: Record<RejectionReason, string> = {
  quote_does_not_support: 'Quote does not support it',
  quote_out_of_context: 'Quote taken out of context',
  too_general: 'Too general to be useful',
  wrong_relationship_type: 'Wrong relationship type',
  not_appropriate_for_patients: 'Not appropriate to surface to patients',
  clinically_incorrect: 'Clinically incorrect',
  duplicate: 'Duplicate',
  chain_does_not_hold: 'Chained quotes do not combine',
};

/** One §5.7 reason a version cannot publish. edge_id is null for
 *  version-level problems (missing governance note, no edges). */
export interface PublicationBlocker {
  edge_id: string | null;
  problem: string;
}

export interface BlockersResponse {
  status: 'ok';
  blockers: PublicationBlocker[];
  publishable: boolean;
}

export function fetchVersionBlockers(versionId: string) {
  return apiFetch<BlockersResponse>(ENDPOINTS.reviewVersionBlockers(versionId), {
    method: 'GET',
  });
}

export function publishVersion(versionId: string) {
  return apiFetch<{ status: 'ok'; version_id: string }>(
    ENDPOINTS.reviewVersionPublish(versionId),
    { method: 'POST' },
  );
}

export function fetchReviewMeta() {
  return apiFetch<ReviewMetaResponse>(ENDPOINTS.reviewMeta, { method: 'GET' });
}

export function fetchReviewQueue(status: string = 'candidate') {
  return apiFetch<ReviewQueueResponse>(
    `${ENDPOINTS.reviewQueue}?status=${encodeURIComponent(status)}`,
    { method: 'GET' },
  );
}

export function rewordEdge(edgeId: string, patientPhrasing: string) {
  return apiFetch<ReviewEditResponse>(ENDPOINTS.reviewEdge(edgeId), {
    method: 'PATCH',
    body: { patient_phrasing: patientPhrasing },
  });
}

export function attestEdge(
  edgeId: string,
  decision: 'approve' | 'reject',
  expectedHash: string,
  rejectionReason?: RejectionReason,
) {
  return apiFetch<ReviewAttestResponse>(ENDPOINTS.reviewAttest(edgeId), {
    method: 'POST',
    body:
      decision === 'reject'
        ? { decision, rejection_reason: rejectionReason, expected_hash: expectedHash }
        : { decision, expected_hash: expectedHash },
  });
}
