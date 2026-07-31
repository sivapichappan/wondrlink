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

  // A secure field must never be autocapitalised or autocorrected. React
  // Native's default autoCapitalize is "sentences", which silently uppercases
  // the FIRST CHARACTER of a typed password — so a password beginning with a
  // lowercase letter cannot be entered on iOS at all, and the user is told
  // "invalid email or password" with no way to work out why. That shipped: five
  // secure fields across login, register and password reset, none of them
  // setting it, while the email field beside them did.
  //
  // Defaulted here rather than at each call site, because the next password
  // field someone adds will forget it too. An explicit prop still wins.
  const secureDefaults = rest.secureTextEntry
    ? {
        autoCapitalize: 'none' as const,
        autoCorrect: false,
        spellCheck: false,
      }
    : null;
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
        {...secureDefaults}
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
