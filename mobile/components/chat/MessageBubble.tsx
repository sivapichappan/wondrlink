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
        {/* The patient's own words — the ONLY warm element on screen
            (redesign 2026-08-24), set in the interface sans, not the voice
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
