import { Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { MarkdownText } from './MarkdownText';

interface Props {
  role: 'user' | 'assistant';
  content: string;
}

export function MessageBubble({ role, content }: Props) {
  if (role === 'user') {
    return (
      <View
        style={{
          alignSelf: 'flex-end',
          maxWidth: '88%',
          backgroundColor: Colors.primary,
          paddingHorizontal: 14,
          paddingVertical: 10,
          borderRadius: Radius.lg,
          borderBottomRightRadius: 4,
        }}>
        <Text style={{ color: Colors.surface, fontSize: 15, lineHeight: 22, fontFamily: Fonts.sans }}>
          {content}
        </Text>
      </View>
    );
  }
  // Bot bubble is rendered inside BotResponseCard — just render markdown.
  return (
    <View style={{ paddingHorizontal: 2 }}>
      <MarkdownText>{content}</MarkdownText>
    </View>
  );
}
