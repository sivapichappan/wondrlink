import { Sparkles } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';

interface Props {
  followups?: string[];
  onPick: (text: string) => void;
}

export function FollowupChips({ followups, onPick }: Props) {
  if (!followups || followups.length === 0) return null;

  return (
    <View style={{ gap: 6 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Sparkles size={12} color={Colors.textMuted} />
        <Text
          style={{
            color: Colors.textMuted,
            fontFamily: Fonts.sansMedium,
            fontSize: 11,
            letterSpacing: 0.5,
          }}>
          KEEP EXPLORING
        </Text>
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {followups.map((q, i) => (
          <Pressable
            key={`${i}-${q.slice(0, 16)}`}
            onPress={() => onPick(q)}
            accessibilityRole="button"
            accessibilityHint="Send this follow-up question"
            style={({ pressed }) => ({
              paddingHorizontal: 12,
              paddingVertical: 8,
              borderRadius: 999,
              backgroundColor: pressed ? Colors.primaryLight : Colors.sidebarBg,
              borderWidth: 1,
              borderColor: pressed ? Colors.primary : Colors.border,
              maxWidth: '100%',
            })}>
            <Text
              style={{
                color: Colors.textPrimary,
                fontFamily: Fonts.sansMedium,
                fontSize: 13,
                lineHeight: 18,
              }}>
              {q}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}
