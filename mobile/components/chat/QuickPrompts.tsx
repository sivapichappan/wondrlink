import { Apple, CalendarClock, Search, Sparkles } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

interface Prompt {
  label: string;
  Icon: typeof Sparkles;
  text: string;
}

const PROMPTS: Prompt[] = [
  {
    label: 'Side effects',
    Icon: Sparkles,
    text: 'What side effects should I expect from my current treatment, and which ones need urgent attention?',
  },
  {
    label: 'Find trials',
    Icon: Search,
    text: 'Are there clinical trials I should consider for my situation?',
  },
  {
    label: 'Prep for visit',
    Icon: CalendarClock,
    text: 'Help me prepare for my next oncology appointment.',
  },
  {
    label: 'Eating during chemo',
    Icon: Apple,
    text: 'What should I eat during chemotherapy to manage side effects and stay nourished?',
  },
];

interface Props {
  onPick: (text: string) => void;
}

export function QuickPrompts({ onPick }: Props) {
  return (
    <View style={styles.container}>
      {PROMPTS.map((p) => (
        <Pressable
          key={p.label}
          onPress={() => onPick(p.text)}
          accessibilityRole="button"
          accessibilityLabel={p.label}
          style={({ pressed }) => [
            styles.card,
            pressed && { backgroundColor: Colors.sidebarBg, borderColor: Colors.primary },
          ]}>
          <View style={styles.row}>
            <p.Icon size={16} color={Colors.primary} style={{ marginRight: 8 }} />
            <Text style={styles.label}>{p.label}</Text>
          </View>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingBottom: 8,
    gap: 8,
  },
  card: {
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  label: {
    color: Colors.textPrimary,
    fontFamily: Fonts.sansMedium,
    fontSize: 14,
  },
});
