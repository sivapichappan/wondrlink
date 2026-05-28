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
    <View style={{ gap: 4 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <Sparkles size={10} color={Colors.textMuted} />
        <Text
          style={{
            color: Colors.textMuted,
            fontFamily: Fonts.sansMedium,
            fontSize: 10,
            letterSpacing: 0.5,
          }}>
          KEEP EXPLORING
        </Text>
      </View>
      <View style={{ gap: 4 }}>
        {followups.map((q, i) => (
          <Pressable
            key={`${i}-${q.slice(0, 16)}`}
            onPress={() => onPick(q)}
            accessibilityRole="button"
            accessibilityLabel={q}
            accessibilityHint="Send this follow-up question"
            style={({ pressed }) => ({
              paddingHorizontal: 10,
              paddingVertical: 6,
              borderRadius: 8,
              backgroundColor: pressed ? Colors.primaryLight : Colors.sidebarBg,
              borderWidth: 1,
              borderColor: pressed ? Colors.primary : Colors.border,
            })}>
            <Text
              numberOfLines={1}
              ellipsizeMode="tail"
              style={{
                color: Colors.textPrimary,
                fontFamily: Fonts.sansMedium,
                fontSize: 12,
                lineHeight: 16,
              }}>
              {q}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}
