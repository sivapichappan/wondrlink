/**
 * Screen — the one place the page gutter lives (Spacing.xl / 20). Kills the
 * 16 vs 20 vs 24 gutter drift at the source: every screen that adopts this gets
 * an identical content inset.
 *
 * Composition: an optional fixed `header` (e.g. TopBar, which owns its own top
 * safe-area inset), a scroll (or static) body with the gutter + a default
 * vertical `gap`, and an optional fixed `footer` (e.g. the chat composer, which
 * owns its own bottom inset). Set `keyboardAvoiding` for composer screens.
 */

import { KeyboardAvoidingView, Platform, ScrollView, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, Spacing } from '@/constants/theme';

interface ScreenProps {
  header?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
  scroll?: boolean;
  gap?: number;
  padded?: boolean;
  keyboardAvoiding?: boolean;
  keyboardShouldPersistTaps?: boolean;
}

export function Screen({
  header,
  footer,
  children,
  scroll = true,
  gap = Spacing.md,
  padded = true,
  keyboardAvoiding = false,
  keyboardShouldPersistTaps = false,
}: ScreenProps) {
  const insets = useSafeAreaInsets();
  const pad = padded ? Spacing.xl : 0;

  const body = scroll ? (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ padding: pad, gap, paddingBottom: footer ? Spacing.md : insets.bottom + Spacing.xl }}
      keyboardShouldPersistTaps={keyboardShouldPersistTaps ? 'handled' : 'never'}
      showsVerticalScrollIndicator={false}>
      {children}
    </ScrollView>
  ) : (
    <View style={{ flex: 1, padding: pad, gap }}>{children}</View>
  );

  const middle = keyboardAvoiding ? (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      {body}
      {footer}
    </KeyboardAvoidingView>
  ) : (
    <>
      {body}
      {footer}
    </>
  );

  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      {header}
      {middle}
    </View>
  );
}
