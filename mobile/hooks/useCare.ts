/**
 * Hooks for the Care surface.
 *
 * useHero: /api/hero — personalized welcome card
 * useCareSnapshot: /api/care_snapshot — PHQ-9 trend + days-since-symptom
 * useProfile: /api/get_patient — full patient profile JSON
 */

import { useQuery } from '@tanstack/react-query';

import { fetchCareSnapshot, fetchHero, fetchProfile } from '@/lib/api/care';

export function useHero() {
  return useQuery({
    queryKey: ['hero'],
    queryFn: fetchHero,
    staleTime: 60_000,
  });
}

export function useCareSnapshot() {
  return useQuery({
    queryKey: ['care_snapshot'],
    queryFn: fetchCareSnapshot,
    staleTime: 60_000,
  });
}

export function useProfile() {
  return useQuery({
    queryKey: ['profile'],
    queryFn: fetchProfile,
    staleTime: 60_000,
  });
}
