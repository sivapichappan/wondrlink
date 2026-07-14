/**
 * TopBar — the shared app-shell header.
 *
 * Two leading modes:
 *   - "menu"  → hamburger that opens the drawer (Home).
 *   - "back"  → a "‹ {label}" button (pushed screens: My Care, All tools, …).
 * The center shows a title (+ optional subtitle) on pushed screens; Home's bar
 * is just the menu button. Help + Cancer focus live in the drawer, not here.
 *
 * NativeWind rule: every Pressable's visual styling lives on a static inner
 * <View>; the Pressable only handles touch.
 */

import { router } from 'expo-router';
import { ChevronLeft, Menu } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, FontSize, Fonts, Spacing } from '@/constants/theme';
import { useNavOverlay } from './NavOverlay';

interface TopBarProps {
  leading?: 'menu' | 'back';
  /** Label beside the back chevron (e.g. "Home", "Chat"). */
  backLabel?: string;
  onBack?: () => void;
  /** Centered title (pushed screens). */
  title?: string;
  subtitle?: string;
  /** Extra control on the right (e.g. a new-chat button on the thread). */
  trailing?: React.ReactNode;
}

export function TopBar({ leading = 'menu', backLabel = 'Back', onBack, title, subtitle, trailing }: TopBarProps) {
  const insets = useSafeAreaInsets();
  const { openDrawer } = useNavOverlay();

  return (
    <View
      style={{
        paddingTop: insets.top + Spacing.sm,
        paddingBottom: Spacing.sm,
        paddingHorizontal: Spacing.md,
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.xs,
        borderBottomWidth: title ? 1 : 0,
        borderBottomColor: Colors.border,
        backgroundColor: Colors.surface,
      }}>
      {/* Leading */}
      {leading === 'menu' ? (
        <Pressable
          onPress={openDrawer}
          accessibilityRole="button"
          accessibilityLabel="Open menu"
          hitSlop={8}
          style={{ width: 38, height: 38, alignItems: 'center', justifyContent: 'center' }}>
          <Menu size={22} color={Colors.textSecondary} />
        </Pressable>
      ) : (
        <Pressable
          onPress={onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/')))}
          accessibilityRole="button"
          accessibilityLabel={`Back to ${backLabel}`}
          hitSlop={8}
          style={{ minWidth: 74, height: 38, flexDirection: 'row', alignItems: 'center' }}>
          <ChevronLeft size={22} color={Colors.primary} />
          <Text style={{ color: Colors.primary, fontSize: FontSize.lg }} numberOfLines={1}>
            {backLabel}
          </Text>
        </Pressable>
      )}

      {/* Center title */}
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        {title ? (
          <>
            <Text numberOfLines={1} style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.xl, color: Colors.textPrimary, maxWidth: 220 }}>
              {title}
            </Text>
            {subtitle ? (
              <Text numberOfLines={1} style={{ fontSize: FontSize.xs, color: Colors.textMuted, marginTop: 1 }}>
                {subtitle}
              </Text>
            ) : null}
          </>
        ) : null}
      </View>

      {/* Trailing */}
      {trailing ?? <View style={{ width: 38 }} />}
    </View>
  );
}
