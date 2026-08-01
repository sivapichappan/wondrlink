import { Eye, EyeOff } from 'lucide-react-native';
import { forwardRef, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View, type TextInputProps } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

interface Props extends TextInputProps {
  label?: string;
  hint?: string;
  error?: string;
}

// Room for the reveal button so typed text never runs underneath it.
const REVEAL_HIT = 44;

export const TextField = forwardRef<TextInput, Props>(function TextField(
  { label, hint, error, onFocus, onBlur, style, ...rest },
  ref,
) {
  const [focused, setFocused] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const borderColor = error ? Colors.danger : focused ? Colors.primary : Colors.border;

  // Whether this is a PASSWORD field, which is not the same as whether the
  // characters are currently hidden. Everything below keys off the former, so
  // revealing the text does not quietly change the keyboard's behaviour.
  const isPassword = !!rest.secureTextEntry;

  // A secure field must never be autocapitalised or autocorrected. React
  // Native's default autoCapitalize is "sentences", which silently uppercases
  // the FIRST CHARACTER of a typed password — so a password beginning with a
  // lowercase letter cannot be entered on iOS at all, and the user is told
  // "invalid email or password" with no way to work out why. That shipped: five
  // secure fields across login, register and password reset, none setting it,
  // while the email field beside them did.
  //
  // Defaulted here rather than at each call site, because the next password
  // field someone adds will forget it too. An explicit prop still wins.
  //
  // Keyed off isPassword, NOT off the current visibility: revealing the text
  // must not re-enable autocapitalise mid-entry.
  const secureDefaults = isPassword
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
      <View style={{ justifyContent: 'center' }}>
        <TextInput
          ref={ref}
          placeholderTextColor={Colors.textMuted}
          {...secureDefaults}
          {...rest}
          // After {...rest} on purpose: the caller sets secureTextEntry to say
          // "this is a password", and the toggle owns whether it is hidden now.
          secureTextEntry={isPassword && !revealed}
          style={StyleSheet.flatten([
            {
              backgroundColor: Colors.surface,
              borderWidth: 1,
              borderColor,
              borderRadius: Radius.sm,
              paddingHorizontal: 12,
              paddingRight: isPassword ? REVEAL_HIT : 12,
              minHeight: 44,
              color: Colors.textPrimary,
              fontSize: 16, // iOS no-zoom
              fontFamily: Fonts.sans,
            },
            style,
          ])}
        />
        {isPassword && (
          <Pressable
            onPress={() => setRevealed((v) => !v)}
            accessibilityRole="button"
            accessibilityLabel={revealed ? 'Hide password' : 'Show password'}
            hitSlop={8}
            // Touch only. Visual styling on a Pressable's pressed-style FUNCTION
            // is silently stripped by NativeWind, which renders the control
            // invisible but still tappable (see .claude/rules/mobile-ui.md).
            style={{ position: 'absolute', right: 0, top: 0, bottom: 0 }}>
            <View
              style={{
                width: REVEAL_HIT,
                height: '100%',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
              {revealed ? (
                <EyeOff size={18} color={Colors.textMuted} />
              ) : (
                <Eye size={18} color={Colors.textMuted} />
              )}
            </View>
          </Pressable>
        )}
      </View>
      {error ? (
        <Text style={{ color: Colors.danger, fontSize: 12 }}>{error}</Text>
      ) : hint ? (
        <Text style={{ color: Colors.textMuted, fontSize: 12 }}>{hint}</Text>
      ) : null}
    </View>
  );
});
