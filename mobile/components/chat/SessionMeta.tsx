/**
 * Per-session AI reminder. Required by CA chatbot law + Utah HB 452 +
 * Tennessee chatbot disclosure law. The persistent banner above the
 * FlatList is shipped already; this is the louder per-session reminder
 * that lands on every new session (post-login or post Clear-History).
 *
 * Parity with the web SESSION_META_HTML shipped in commit 41b11b1.
 */

import { Bot } from 'lucide-react-native';
import { Platform, Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';

const COPY =
  "Session started — you're chatting with an AI assistant, not a person. " +
  'AI can make mistakes. Verify anything important with your care team.';

export function SessionMeta() {
  return (
    <View
      accessibilityRole={Platform.OS === 'android' ? 'alert' : undefined}
      accessibilityLiveRegion="polite"
      accessibilityLabel={COPY}
      style={{
        marginHorizontal: 24,
        marginTop: 12,
        marginBottom: 4,
        paddingVertical: 8,
        paddingHorizontal: 14,
        borderRadius: 999,
        backgroundColor: Colors.sidebarBg,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        alignSelf: 'center',
      }}>
      <Bot size={13} color={Colors.primary} />
      <Text
        style={{
          flexShrink: 1,
          color: Colors.textSecondary,
          fontSize: 11.5,
          lineHeight: 16,
          textAlign: 'center',
          fontFamily: Fonts.sans,
        }}>
        {COPY}
      </Text>
    </View>
  );
}
