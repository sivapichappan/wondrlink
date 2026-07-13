import { Stack } from 'expo-router';

import { HeaderBack } from '@/components/common/HeaderBack';
import { HeaderSos } from '@/components/common/HeaderSos';
import { Colors } from '@/constants/theme';

export default function ToolsLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
        animation: 'slide_from_right',
        animationDuration: 250,
        headerLeft: () => <HeaderBack label="Tools" />,
        headerRight: () => <HeaderSos />,
      }}
    />
  );
}
