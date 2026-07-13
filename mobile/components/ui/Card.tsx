/**
 * Card — the one card recipe, two fills. Replaces the four ad-hoc card styles
 * (bordered-surface / bordered-muted / borderless-tinted / accent) that drifted
 * across screens. `bordered` = house style (border + Radius.lg + surface);
 * `muted` = same on surfaceMuted. Tappable variant keeps visuals on a static
 * inner View (NativeWind rule) by making the Pressable a thin wrapper.
 */

import { Pressable, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';

interface CardProps {
  variant?: 'bordered' | 'muted';
  padding?: number;
  gap?: number;
  onPress?: () => void;
  accessibilityLabel?: string;
  style?: object;
  children: React.ReactNode;
}

export function Card({
  variant = 'bordered',
  padding = Spacing.lg,
  gap,
  onPress,
  accessibilityLabel,
  style,
  children,
}: CardProps) {
  const surface = (
    <View
      style={[
        {
          backgroundColor: variant === 'muted' ? Colors.surfaceMuted : Colors.surface,
          borderWidth: 1,
          borderColor: Colors.border,
          borderRadius: Radius.lg,
          padding,
          gap,
        },
        style,
      ]}>
      {children}
    </View>
  );

  if (!onPress) return surface;
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={accessibilityLabel}>
      {surface}
    </Pressable>
  );
}
