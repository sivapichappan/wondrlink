import { Stack, router } from 'expo-router';
import { useEffect } from 'react';
import { View } from 'react-native';

import { Colors } from '@/constants/theme';

/**
 * The full Consumer Health Data Privacy Notice is rendered by
 * app/(onboarding)/disclaimer.tsx. Settings -> Health Notice routes there so
 * we don't duplicate the long-form legal copy.
 */
export default function HealthNotice() {
  useEffect(() => {
    router.replace('/(onboarding)/disclaimer');
  }, []);
  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      <Stack.Screen options={{ title: 'Consumer Health Data Privacy Notice' }} />
    </View>
  );
}
