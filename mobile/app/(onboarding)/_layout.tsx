import { Stack } from 'expo-router';

import { Colors } from '@/constants/theme';

export default function OnboardingLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
        gestureEnabled: false,
        // iOS falls back to the previous ROUTE NAME ("who-for") as the back
        // label when that screen has no title — always say Back instead.
        headerBackTitle: 'Back',
      }}>
      <Stack.Screen name="reviewer-apply" options={{ title: 'Reviewer access' }} />
      {/* No back: a submitted application is not something to navigate out of,
          and there is nowhere behind this screen a reviewer account may go. */}
      <Stack.Screen
        name="reviewer-pending"
        options={{ title: 'Waiting on us', headerBackVisible: false }}
      />
      <Stack.Screen name="consent" options={{ title: 'Before you start', headerBackVisible: false }} />
      <Stack.Screen name="disclaimer" options={{ title: 'Privacy Notice' }} />
      <Stack.Screen name="who-for" options={{ headerShown: false }} />
      <Stack.Screen
        name="state-restricted"
        options={{ title: 'Not available', headerBackVisible: false }}
      />
    </Stack>
  );
}
