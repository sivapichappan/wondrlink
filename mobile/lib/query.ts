/**
 * TanStack Query client.
 *
 * Single instance shared across the app. Defaults tuned for a chat / RAG
 * surface where stale-while-revalidate is fine for most endpoints but
 * we never want stale chat responses (those are explicitly mutated).
 */

import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
