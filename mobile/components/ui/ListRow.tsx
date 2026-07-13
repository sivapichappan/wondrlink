/**
 * ListRow — one row archetype at one height. Replaces the 36/38/40/42 row
 * heights and mixed fills scattered across the drawer, My Care, settings, etc.
 * Leading icon slot · title (+ optional subtitle) · optional value/right · chevron.
 * Pressable is a thin wrapper; visuals live on the static inner View.
 */

import { ChevronRight } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';

import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';

interface ListRowProps {
  icon?: React.ReactNode;
  title: string;
  subtitle?: string;
  value?: string;
  right?: React.ReactNode;
  chevron?: boolean;
  onPress?: () => void;
  tintTitle?: boolean;
  fill?: 'none' | 'muted' | 'sidebar';
  accessibilityLabel?: string;
}

const FILLS = {
  none: 'transparent',
  muted: Colors.surfaceMuted,
  sidebar: Colors.sidebarBg,
} as const;

export function ListRow({
  icon,
  title,
  subtitle,
  value,
  right,
  chevron = true,
  onPress,
  tintTitle,
  fill = 'none',
  accessibilityLabel,
}: ListRowProps) {
  const body = (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.md,
        minHeight: 48,
        paddingHorizontal: Spacing.md,
        paddingVertical: Spacing.sm,
        borderRadius: fill === 'none' ? 0 : Radius.sm,
        backgroundColor: FILLS[fill],
      }}>
      {icon}
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text
          numberOfLines={1}
          style={{
            fontSize: FontSize.md,
            fontFamily: tintTitle ? Fonts.sansSemiBold : Fonts.sans,
            color: tintTitle ? Colors.primary : Colors.textPrimary,
          }}>
          {title}
        </Text>
        {subtitle ? (
          <Text numberOfLines={1} style={{ fontSize: FontSize.sm, color: Colors.textMuted, marginTop: 1 }}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {value ? <Text style={{ fontSize: FontSize.sm, color: Colors.textMuted }}>{value}</Text> : null}
      {right}
      {chevron ? <ChevronRight size={18} color={Colors.primary} /> : null}
    </View>
  );

  if (!onPress) return body;
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={accessibilityLabel ?? title}>
      {body}
    </Pressable>
  );
}
