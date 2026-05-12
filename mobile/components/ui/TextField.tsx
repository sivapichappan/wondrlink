import { forwardRef, useState } from 'react';
import { StyleSheet, Text, TextInput, View, type TextInputProps } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

interface Props extends TextInputProps {
  label?: string;
  hint?: string;
  error?: string;
}

export const TextField = forwardRef<TextInput, Props>(function TextField(
  { label, hint, error, onFocus, onBlur, style, ...rest },
  ref,
) {
  const [focused, setFocused] = useState(false);
  const borderColor = error ? Colors.danger : focused ? Colors.primary : Colors.border;
  return (
    <View style={{ gap: 6 }}>
      {label && (
        <Text style={{ color: Colors.textSecondary, fontSize: 12, fontFamily: Fonts.sansMedium }}>
          {label}
        </Text>
      )}
      <TextInput
        ref={ref}
        placeholderTextColor={Colors.textMuted}
        onFocus={(e) => {
          setFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          onBlur?.(e);
        }}
        style={StyleSheet.flatten([
          {
            backgroundColor: Colors.surface,
            borderWidth: 1,
            borderColor,
            borderRadius: Radius.sm,
            paddingHorizontal: 12,
            minHeight: 44,
            color: Colors.textPrimary,
            fontSize: 16, // iOS no-zoom
            fontFamily: Fonts.sans,
          },
          style,
        ])}
        {...rest}
      />
      {error ? (
        <Text style={{ color: Colors.danger, fontSize: 12 }}>{error}</Text>
      ) : hint ? (
        <Text style={{ color: Colors.textMuted, fontSize: 12 }}>{hint}</Text>
      ) : null}
    </View>
  );
});
