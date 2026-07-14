import { Stack } from 'expo-router';

import { HeaderBack } from '@/components/common/HeaderBack';
import { Colors } from '@/constants/theme';

export default function SettingsLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
        animation: 'slide_from_right',
        animationDuration: 250,
        headerLeft: () => <HeaderBack label="Settings" />,
      }}
    />
  );
}
