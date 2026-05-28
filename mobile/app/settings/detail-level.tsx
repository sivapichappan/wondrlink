import { Stack } from 'expo-router';
import { Check } from 'lucide-react-native';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { useResponseLength } from '@/hooks/useResponseLength';
import type { ResponseLength } from '@shared/types';

interface Option {
  key: ResponseLength;
  title: string;
  blurb: string;
}

const OPTIONS: Option[] = [
  {
    key: 'brief',
    title: 'Brief',
    blurb: 'Short, 2–3 sentence answers. Best when you just need the headline.',
  },
  {
    key: 'normal',
    title: 'Normal',
    blurb: 'Balanced answers with the key details. Recommended for most questions.',
  },
  {
    key: 'detailed',
    title: 'Detailed',
    blurb:
      'Longer, comprehensive answers with full context. Best for treatment + biomarker deep-dives.',
  },
];

export default function DetailLevelScreen() {
  const { responseLength, setResponseLength } = useResponseLength();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['bottom']}>
      <Stack.Screen options={{ title: 'Detail level' }} />
      <ScrollView contentContainerStyle={{ padding: 20, gap: 14, paddingBottom: 40 }}>
        <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 21 }}>
          Controls how long WondrChat's answers tend to be. Applies to every new chat message —
          you can change it any time.
        </Text>

        {OPTIONS.map((opt) => {
          const selected = responseLength === opt.key;
          return (
            <Pressable
              key={opt.key}
              onPress={() => setResponseLength(opt.key)}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              style={({ pressed }) => ({
                borderRadius: Radius.lg,
                borderWidth: selected ? 2 : 1,
                borderColor: selected ? Colors.primary : Colors.border,
                backgroundColor: selected
                  ? Colors.sidebarBg
                  : pressed
                    ? Colors.surfaceMuted
                    : Colors.surface,
              })}>
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'flex-start',
                  padding: 16,
                }}>
                <View style={{ flex: 1 }}>
                  <Text
                    style={{
                      color: selected ? Colors.primary : Colors.textPrimary,
                      fontFamily: Fonts.sansSemiBold,
                      fontSize: 16,
                    }}>
                    {opt.title}
                  </Text>
                  <Text
                    style={{
                      color: Colors.textSecondary,
                      fontSize: 13,
                      lineHeight: 19,
                      marginTop: 4,
                    }}>
                    {opt.blurb}
                  </Text>
                </View>
                {selected && (
                  <Check size={20} color={Colors.primary} style={{ marginLeft: 12, marginTop: 2 }} />
                )}
              </View>
            </Pressable>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}
