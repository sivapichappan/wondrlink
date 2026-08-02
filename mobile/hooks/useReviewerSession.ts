/**
 * Who this session is, in reviewer terms.
 *
 * Three outcomes, not two. A pending applicant is neither a reviewer nor a
 * patient: routing them into patient onboarding would end in a patient profile,
 * which is the one thing a reviewer account may never hold. Before the server
 * carried a status they were indistinguishable from a stranger, so patient
 * onboarding was the only place the app could send them.
 *
 * Reads the acknowledgement query that already runs on every launch, so this
 * costs no extra request.
 */

import { useAcknowledgement } from './useAcknowledgement';

export type ReviewerStatus = 'requested' | 'invited' | 'active' | 'revoked' | null;

export function useReviewerSession() {
  const ack = useAcknowledgement();
  const data = ack.data;

  // is_reviewer keeps meaning ACTIVE server-side, so it is the fallback when an
  // older server sends no status at all.
  const status: ReviewerStatus =
    (data?.reviewer_status as ReviewerStatus) ?? (data?.is_reviewer ? 'active' : null);

  return {
    /** Approved. Gets the whole app, plus Approvals in the drawer. */
    isReviewer: status === 'active',
    /** Applied and waiting. Gets the pending screen and nothing else. */
    isPending: status === 'requested' || status === 'invited',
    /** Also sees the applications dashboard. */
    isAdmin: data?.reviewer_role === 'admin' && status === 'active',
    /** Only an attesting physician may sign (§5.1). */
    canAttest: data?.reviewer_role === 'reviewer_attesting' && status === 'active',
    status,
    role: data?.reviewer_role ?? null,
    /** Nothing is known yet — branch on this before deciding anything. */
    isLoading: ack.sessionLoading || (ack.hasSession && ack.isLoading) || !data,
  };
}
