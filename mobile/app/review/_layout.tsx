/**
 * Review workspace stack (SPEC-connection-map.md §5.4, adapted phone-first).
 *
 * Reviewer accounts only. RootGate routes reviewers here and patients away,
 * but this layout self-gates too: if the acknowledgement says this session is
 * not a reviewer, render a redirect home rather than trusting navigation
 * order. The real boundary is server-side either way — every /api/review/*
 * call runs on the restricted sage_review role and answers 403 to anyone
 * else — so this gate is UX, not security.
 */

import { Redirect, Stack } from 'expo-router';

import { Colors } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';

export default function ReviewLayout() {
  const ack = useAcknowledgement();

  if (ack.data && !ack.data.is_reviewer) {
    return <Redirect href="/" />;
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
      }}>
      <Stack.Screen name="index" options={{ title: 'Review queue' }} />
    </Stack>
  );
}
