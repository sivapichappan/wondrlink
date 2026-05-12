import { Stack } from 'expo-router';

import { Colors } from '@/constants/theme';

export default function ToolsLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
        headerBackTitle: 'Back',
      }}
    />
  );
}
