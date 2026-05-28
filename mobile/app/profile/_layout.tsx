import { Stack } from 'expo-router';

import { HeaderBack } from '@/components/common/HeaderBack';
import { Colors } from '@/constants/theme';

export default function ProfileLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
      }}>
      <Stack.Screen
        name="index"
        options={{
          title: 'Profile',
          headerLeft: () => <HeaderBack label="Back" />,
        }}
      />
      <Stack.Screen
        name="build"
        options={{
          title: 'Build profile',
          headerLeft: () => <HeaderBack label="Profile" />,
        }}
      />
      <Stack.Screen
        name="cancer-switcher"
        options={{
          title: 'Cancer focus',
          headerLeft: () => <HeaderBack label="Profile" />,
        }}
      />
    </Stack>
  );
}
