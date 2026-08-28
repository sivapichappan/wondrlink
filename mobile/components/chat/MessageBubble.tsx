import { Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { MarkdownText } from './MarkdownText';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  /** Long press opens the select-text sheet. */
  onSelectText?: (content: string) => void;
}

export function MessageBubble({ role, content, onSelectText }: Props) {
  if (role === 'user') {
    return (
      // No `selectable` here. On iOS it only ever offered "copy the whole
      // bubble", and it installs a native long-press recognizer that would
      // fight the one below for the same gesture. See SelectTextSheet.
      <Pressable
        onLongPress={onSelectText ? () => onSelectText(content) : undefined}
        delayLongPress={350}
        accessibilityHint="Press and hold to copy or select text"
        style={{ alignSelf: 'flex-end', maxWidth: '88%' }}>
        {/* The patient's own words — the one light in the room. Kept from
            the approved design, which had the idea right; only the hue
            moved, warm beige to pale blue, so one accent family serves both
            the day and the night ground. Interface sans, not the voice
            serif: typography says who is speaking. */}
        <View
          style={{
            backgroundColor: Colors.warmBubble,
            borderWidth: 1,
            borderColor: Colors.warmBubbleBorder,
            paddingHorizontal: 14,
            paddingVertical: 10,
            borderRadius: Radius.lg,
            borderBottomRightRadius: 6,
            // A faint bloom, not a glow: a coloured halo is the tell this
            // product should sit furthest from.
            shadowColor: Colors.primary,
            shadowOpacity: 0.1,
            shadowRadius: 14,
            shadowOffset: { width: 0, height: 2 },
          }}>
          <Text style={{ color: Colors.warmBubbleInk, fontSize: 15, lineHeight: 22, fontFamily: Fonts.sans }}>
            {content}
          </Text>
        </View>
      </Pressable>
    );
  }
  // Bot bubble is rendered inside BotResponseCard — just render markdown.
  return (
    <View style={{ paddingHorizontal: 2 }}>
      <MarkdownText>{content}</MarkdownText>
    </View>
  );
}
