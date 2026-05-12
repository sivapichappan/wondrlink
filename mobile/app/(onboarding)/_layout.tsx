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
      }}>
      <Stack.Screen name="consent" options={{ title: 'Before you start', headerBackVisible: false }} />
      <Stack.Screen name="disclaimer" options={{ title: 'Privacy Notice' }} />
      <Stack.Screen
        name="state-restricted"
        options={{ title: 'Not available', headerBackVisible: false }}
      />
    </Stack>
  );
}
