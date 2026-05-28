import { router } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';

export function HeaderBack({ label = 'Back' }: { label?: string }) {
  return (
    <Pressable
      onPress={() => router.back()}
      accessibilityRole="button"
      accessibilityLabel="Go back"
      hitSlop={8}
      style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          paddingVertical: 6,
          paddingRight: 8,
        }}>
        <ChevronLeft size={22} color={Colors.primary} />
        <Text
          style={{
            color: Colors.primary,
            fontFamily: Fonts.sansMedium,
            fontSize: 16,
            marginLeft: -2,
          }}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}
