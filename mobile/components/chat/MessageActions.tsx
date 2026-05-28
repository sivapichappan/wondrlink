import * as Clipboard from 'expo-clipboard';
import { Check, Copy, ThumbsDown, ThumbsUp } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';
import { submitFeedback } from '@/lib/api/account';

interface Props {
  messageText: string;
}

type Rating = 'up' | 'down';

export function MessageActions({ messageText }: Props) {
  const [rating, setRating] = useState<Rating | null>(null);
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await Clipboard.setStringAsync(messageText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // best-effort
    }
  };

  const onRate = async (r: Rating) => {
    if (rating === r) return;
    setRating(r);
    try {
      await submitFeedback({ rating: r, message_preview: messageText.slice(0, 200) });
    } catch {
      // best-effort — keep the optimistic UI
    }
  };

  return (
    <View style={styles.row}>
      <ActionButton
        active={rating === 'up'}
        onPress={() => onRate('up')}
        accessibilityLabel="Mark response as helpful">
        <ThumbsUp size={14} color={rating === 'up' ? Colors.primary : Colors.textMuted} />
      </ActionButton>
      <ActionButton
        active={rating === 'down'}
        onPress={() => onRate('down')}
        accessibilityLabel="Mark response as unhelpful">
        <ThumbsDown size={14} color={rating === 'down' ? Colors.danger : Colors.textMuted} />
      </ActionButton>
      <ActionButton onPress={onCopy} accessibilityLabel="Copy response">
        {copied ? (
          <View style={styles.copiedRow}>
            <Check size={14} color={Colors.primary} />
            <Text style={styles.copiedText}>Copied</Text>
          </View>
        ) : (
          <Copy size={14} color={Colors.textMuted} />
        )}
      </ActionButton>
    </View>
  );
}

function ActionButton({
  children,
  onPress,
  active,
  accessibilityLabel,
}: {
  children: React.ReactNode;
  onPress: () => void;
  active?: boolean;
  accessibilityLabel: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      hitSlop={6}
      style={({ pressed }) => [
        styles.btn,
        active && styles.btnActive,
        pressed && styles.btnPressed,
      ]}>
      {children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 2,
  },
  btn: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  btnActive: {
    backgroundColor: Colors.sidebarBg,
    borderColor: Colors.primary,
  },
  btnPressed: {
    backgroundColor: Colors.surfaceMuted,
  },
  copiedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  copiedText: {
    color: Colors.primary,
    fontFamily: Fonts.sansSemiBold,
    fontSize: 11,
  },
});
