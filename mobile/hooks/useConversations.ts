/**
 * useConversations — the drawer's Recents list + conversation mutations.
 *
 * Query key ['conversations'] is invalidated whenever a turn creates/renames a
 * conversation (see useChat) so Recents stays fresh.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createConversation,
  deleteConversation,
  fetchConversations,
  renameConversation,
} from '@/lib/api/conversations';

export const CONVERSATIONS_KEY = ['conversations'] as const;

export function useConversations() {
  const qc = useQueryClient();

  const list = useQuery({
    queryKey: CONVERSATIONS_KEY,
    queryFn: () => fetchConversations(),
    staleTime: 15_000,
  });

  const create = useMutation({
    mutationFn: (title?: string) => createConversation(title),
    onSuccess: () => qc.invalidateQueries({ queryKey: CONVERSATIONS_KEY }),
  });

  const rename = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameConversation(id, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: CONVERSATIONS_KEY }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: CONVERSATIONS_KEY }),
  });

  return {
    conversations: list.data ?? [],
    isLoading: list.isLoading,
    error: list.error,
    refetch: list.refetch,
    createConversation: create.mutateAsync,
    renameConversation: rename.mutate,
    deleteConversation: remove.mutate,
  };
}
