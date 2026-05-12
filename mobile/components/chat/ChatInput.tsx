import { Send } from 'lucide-react-native';
import { useState } from 'react';
import { Platform, Pressable, Text, TextInput, View } from 'react-native';

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
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'flex-end',
        gap: 8,
        paddingHorizontal: 12,
        paddingVertical: 10,
        backgroundColor: Colors.surface,
        borderTopWidth: 1,
        borderTopColor: Colors.border,
      }}>
      <View style={{ flex: 1, gap: 4 }}>
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
          style={{
            minHeight: 44,
            maxHeight: 140,
            paddingHorizontal: 12,
            paddingTop: 12,
            paddingBottom: 12,
            backgroundColor: Colors.surfaceMuted,
            borderRadius: Radius.md,
            color: Colors.textPrimary,
            fontSize: 16,
            fontFamily: Fonts.sans,
            lineHeight: 22,
          }}
        />
        {overflow && (
          <View
            style={{
              alignSelf: 'flex-end',
              paddingHorizontal: 8,
              paddingVertical: 2,
              borderRadius: 999,
              backgroundColor: Colors.danger,
            }}>
            <Text style={{ color: Colors.surface, fontSize: 11, fontFamily: Fonts.sansSemiBold }}>
              {text.length} / {MAX_CHARS}
            </Text>
          </View>
        )}
      </View>

      <Pressable
        onPress={submit}
        disabled={!canSend}
        accessibilityRole="button"
        accessibilityLabel="Send message"
        accessibilityState={{ disabled: !canSend }}
        style={({ pressed }) => ({
          width: 44,
          height: 44,
          borderRadius: 22,
          backgroundColor: canSend ? (pressed ? Colors.primaryLight : Colors.primary) : Colors.border,
          alignItems: 'center',
          justifyContent: 'center',
        })}>
        <Send size={20} color={Colors.surface} />
      </Pressable>
    </View>
  );
}
