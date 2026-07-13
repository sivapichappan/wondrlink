import { Stack } from 'expo-router';

import { HeaderBack } from '@/components/common/HeaderBack';
import { HeaderSos } from '@/components/common/HeaderSos';
import { Colors } from '@/constants/theme';

export default function SettingsLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
        headerLeft: () => <HeaderBack label="Settings" />,
        headerRight: () => <HeaderSos />,
      }}
    />
  );
}
