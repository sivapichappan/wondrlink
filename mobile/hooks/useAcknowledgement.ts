/**
 * useAcknowledgement — wraps /api/check_acknowledgement as a TanStack Query.
 * Only fires when there's a Supabase session.
 */

import { useQuery } from '@tanstack/react-query';

import { checkAcknowledgement } from '@/lib/api/consent';
import { useAuth } from './useAuth';

export function useAcknowledgement() {
  const { session, loading: sessionLoading } = useAuth();
  const query = useQuery({
    queryKey: ['acknowledgement', session?.user.id],
    queryFn: checkAcknowledgement,
    enabled: !!session && !sessionLoading,
    staleTime: 60_000,
  });
  return {
    ...query,
    sessionLoading,
    hasSession: !!session,
  };
}
