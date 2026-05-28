import { Mic, Send } from 'lucide-react-native';
import { useState } from 'react';
import {
  Alert,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

const MAX_CHARS = 2000;

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, disabled, placeholder = 'Ask about colon cancer…' }: Props) {
  const [text, setText] = useState('');
  const overflow = text.length > MAX_CHARS;
  const canSend = !disabled && text.trim().length > 0 && !overflow;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText('');
  };

  return (
    <View style={styles.bar}>
      <View style={styles.row}>
        <MicButton />

        <View style={styles.inputCol}>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder={placeholder}
            placeholderTextColor={Colors.textMuted}
            multiline
            editable={!disabled}
            blurOnSubmit={false}
            returnKeyType={Platform.OS === 'ios' ? 'default' : 'send'}
            onSubmitEditing={Platform.OS === 'android' ? submit : undefined}
            style={styles.input}
          />
          {overflow && (
            <View style={styles.overflowChip}>
              <Text style={styles.overflowText}>
                {text.length} / {MAX_CHARS}
              </Text>
            </View>
          )}
        </View>

        <SendButton canSend={canSend} onPress={submit} />
      </View>
    </View>
  );
}

function MicButton() {
  return (
    <View style={styles.micCircle}>
      <View style={styles.iconCenter} pointerEvents="none">
        <Mic size={20} color={Colors.primary} strokeWidth={2} />
      </View>
      <Pressable
        onPress={openMicHint}
        accessibilityRole="button"
        accessibilityLabel="Voice input"
        hitSlop={8}
        style={styles.pressOverlay}
        android_ripple={{ color: Colors.sidebarBg, borderless: true }}
      />
    </View>
  );
}

function SendButton({ canSend, onPress }: { canSend: boolean; onPress: () => void }) {
  return (
    <View
      style={[
        styles.sendCircle,
        {
          backgroundColor: canSend ? Colors.accent : Colors.sidebarBg,
          borderColor: canSend ? Colors.accent : Colors.border,
          shadowOpacity: canSend ? 0.3 : 0,
          elevation: canSend ? 4 : 0,
        },
      ]}>
      <View style={styles.iconCenter} pointerEvents="none">
        <Send
          size={20}
          color={canSend ? Colors.surface : Colors.textMuted}
          strokeWidth={2.4}
          style={{ marginLeft: -2 }}
        />
      </View>
      <Pressable
        onPress={onPress}
        disabled={!canSend}
        accessibilityRole="button"
        accessibilityLabel="Send message"
        accessibilityState={{ disabled: !canSend }}
        hitSlop={8}
        style={styles.pressOverlay}
        android_ripple={{ color: 'rgba(255,255,255,0.25)', borderless: true }}
      />
    </View>
  );
}

function openMicHint() {
  Alert.alert(
    'Voice input',
    'Live voice transcription is coming soon. For now, tap the microphone on your iPhone keyboard to dictate.',
    [{ text: 'Got it' }],
  );
}

const styles = StyleSheet.create({
  bar: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: Colors.surface,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  inputCol: {
    flex: 1,
    minWidth: 0,
    marginHorizontal: 8,
  },
  input: {
    minHeight: 44,
    maxHeight: 140,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 12,
    backgroundColor: Colors.surfaceMuted,
    borderRadius: Radius.md,
    color: Colors.textPrimary,
    fontSize: 16,
    fontFamily: Fonts.sans,
    lineHeight: 22,
  },
  overflowChip: {
    alignSelf: 'flex-end',
    marginTop: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
    backgroundColor: Colors.danger,
  },
  overflowText: {
    color: Colors.surface,
    fontSize: 11,
    fontFamily: Fonts.sansSemiBold,
  },
  micCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    overflow: 'hidden',
    position: 'relative',
  },
  sendCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    overflow: 'hidden',
    position: 'relative',
    shadowColor: Colors.accent,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
  },
  iconCenter: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
});
