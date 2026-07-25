/**
 * useGlossary — the personal term dictionary's saved list + mutations.
 *
 * Mirrors useConversations: one query key, every mutation invalidates it.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  deleteGlossaryTerm,
  listGlossaryTerms,
  saveGlossaryTerm,
  updateGlossaryTerm,
} from '@/lib/api/tools';

export const GLOSSARY_KEY = ['glossary'] as const;

export function useGlossary() {
  const qc = useQueryClient();

  const list = useQuery({
    queryKey: GLOSSARY_KEY,
    queryFn: async () => (await listGlossaryTerms()).terms,
    staleTime: 15_000,
  });

  const add = useMutation({
    mutationFn: ({ term, definition }: { term: string; definition: string }) =>
      saveGlossaryTerm(term, definition),
    onSuccess: () => qc.invalidateQueries({ queryKey: GLOSSARY_KEY }),
  });

  const update = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { term?: string; definition?: string } }) =>
      updateGlossaryTerm(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: GLOSSARY_KEY }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteGlossaryTerm(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: GLOSSARY_KEY }),
  });

  return {
    terms: list.data ?? [],
    isLoading: list.isLoading,
    error: list.error,
    refetch: list.refetch,
    addTerm: add.mutateAsync,
    adding: add.isPending,
    updateTerm: update.mutateAsync,
    updating: update.isPending,
    removeTerm: remove.mutate,
  };
}
