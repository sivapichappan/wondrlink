/**
 * TopBar — the shared app-shell header.
 *
 * Replaces the ~5 hand-rolled inline headers the tab screens each carried.
 * Two leading modes:
 *   - "menu"  → hamburger that opens the drawer (Home).
 *   - "back"  → a "‹ {label}" button (pushed screens: My Care, All tools, …).
 * The center shows either the cancer-focus chip (Home) or a title (+subtitle).
 * The SOS/Help pill is always present on the right and opens the Help sheet.
 *
 * NativeWind rule: every Pressable's visual styling lives on a static inner
 * <View>; the Pressable only handles touch.
 */

import { router } from 'expo-router';
import { ChevronLeft, ChevronsUpDown, LifeBuoy, Menu, Tag } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, FontSize, Fonts, Radius } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useNavOverlay } from './NavOverlay';

interface TopBarProps {
  leading?: 'menu' | 'back';
  /** Label beside the back chevron (e.g. "Home", "Chat"). */
  backLabel?: string;
  onBack?: () => void;
  /** Centered title. When omitted with leading="menu", the focus chip shows. */
  title?: string;
  subtitle?: string;
  /** Force the cancer-focus chip in the center (Home). */
  showFocusChip?: boolean;
  /** Extra control left of the SOS pill (e.g. a new-chat button). */
  trailing?: React.ReactNode;
}

export function TopBar({
  leading = 'menu',
  backLabel = 'Back',
  onBack,
  title,
  subtitle,
  showFocusChip,
  trailing,
}: TopBarProps) {
  const insets = useSafeAreaInsets();
  const { openDrawer, openHelp } = useNavOverlay();

  return (
    <View
      style={{
        paddingTop: insets.top + 8,
        paddingBottom: 10,
        paddingHorizontal: 12,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
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
          onPress={onBack ?? (() => router.back())}
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

      {/* Center */}
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        {title ? (
          <>
            <Text
              numberOfLines={1}
              style={{
                fontFamily: Fonts.serifBold,
                fontSize: FontSize.xl,
                color: Colors.textPrimary,
                maxWidth: 200,
              }}>
              {title}
            </Text>
            {subtitle ? (
              <Text numberOfLines={1} style={{ fontSize: FontSize.xs, color: Colors.textMuted, marginTop: 1 }}>
                {subtitle}
              </Text>
            ) : null}
          </>
        ) : showFocusChip ? (
          <FocusChip />
        ) : null}
      </View>

      {/* Trailing + SOS */}
      {trailing}
      <SosPill onPress={openHelp} />
    </View>
  );
}

function FocusChip() {
  const ack = useAcknowledgement();
  const label = ack.data?.cancer_display ?? 'Pick cancer';
  return (
    <Pressable
      onPress={() => router.push('/profile/cancer-switcher')}
      accessibilityRole="button"
      accessibilityLabel={`Cancer focus: ${label}. Tap to change.`}
      hitSlop={6}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 5,
          paddingHorizontal: 11,
          paddingVertical: 6,
          borderWidth: 1,
          borderColor: Colors.border,
          borderRadius: Radius.pill,
        }}>
        <Tag size={12} color={Colors.primary} />
        <Text
          numberOfLines={1}
          style={{ color: Colors.primary, fontSize: FontSize.sm, fontFamily: Fonts.sansMedium, maxWidth: 160 }}>
          {label}
        </Text>
        <ChevronsUpDown size={12} color={Colors.textMuted} />
      </View>
    </Pressable>
  );
}

/** The persistent SOS/Help pill. Exported so screens can drop it in directly. */
export function SosPill({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="Get help and crisis resources"
      hitSlop={6}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 5,
          paddingHorizontal: 11,
          paddingVertical: 7,
          borderRadius: Radius.pill,
          backgroundColor: Colors.sosBg,
          borderWidth: 1,
          borderColor: Colors.sosBorder,
        }}>
        <LifeBuoy size={14} color={Colors.warning} />
        <Text style={{ color: Colors.warning, fontSize: FontSize.sm, fontFamily: Fonts.sansSemiBold }}>Help</Text>
      </View>
    </Pressable>
  );
}
