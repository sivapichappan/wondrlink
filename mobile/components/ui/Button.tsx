import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
  type PressableProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { PressableScale } from '@/components/ui/PressableScale';
import { Colors, Fonts, Radius } from '@/constants/theme';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

// 'style' is re-declared rather than inherited: a Pressable's style may be a
// FUNCTION, and that function is exactly what NativeWind strips. Callers pass
// layout here (flex, alignSelf) and it lands on the outer container, which is
// where position-in-parent belongs.
interface Props extends Omit<PressableProps, 'children' | 'style'> {
  style?: StyleProp<ViewStyle>;
  label: string;
  onPress?: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  disabled?: boolean;
  leadingIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
  fullWidth?: boolean;
}

const sizes: Record<Size, { paddingV: number; paddingH: number; font: number; minHeight: number }> = {
  sm: { paddingV: 8, paddingH: 12, font: 13, minHeight: 36 },
  md: { paddingV: 12, paddingH: 16, font: 15, minHeight: 44 },
  lg: { paddingV: 14, paddingH: 20, font: 16, minHeight: 50 },
};

interface Theme {
  bg: string;
  fg: string;
  border: string;
  borderWidth: number;
}

function themeFor(variant: Variant, isDisabled: boolean): Theme {
  if (variant === 'primary') {
    return {
      bg: isDisabled ? Colors.surfaceMuted : Colors.primary,
      fg: isDisabled ? Colors.textMuted : Colors.surface,
      border: isDisabled ? Colors.border : Colors.primary,
      borderWidth: 1,
    };
  }
  if (variant === 'secondary') {
    return {
      bg: Colors.surface,
      fg: isDisabled ? Colors.textMuted : Colors.primary,
      border: isDisabled ? Colors.border : Colors.primary,
      borderWidth: 1,
    };
  }
  if (variant === 'danger') {
    return {
      bg: isDisabled ? Colors.surfaceMuted : Colors.danger,
      fg: isDisabled ? Colors.textMuted : Colors.surface,
      border: isDisabled ? Colors.border : Colors.danger,
      borderWidth: 1,
    };
  }
  // Ghost — visible tinted chip.
  return {
    bg: Colors.sidebarBg,
    fg: isDisabled ? Colors.textMuted : Colors.primary,
    border: Colors.border,
    borderWidth: 1,
  };
}

export function Button({
  label,
  onPress,
  variant = 'primary',
  size = 'md',
  loading,
  disabled,
  leadingIcon,
  trailingIcon,
  fullWidth,
  style,
  ...rest
}: Props) {
  const isDisabled = disabled || loading;
  const s = sizes[size];
  const t = themeFor(variant, !!isDisabled);

  const filled = variant === 'primary' || variant === 'danger';
  const shadow =
    filled && !isDisabled
      ? {
          shadowColor: variant === 'danger' ? Colors.danger : Colors.primary,
          shadowOpacity: 0.2,
          shadowRadius: 6,
          shadowOffset: { width: 0, height: 2 },
          elevation: 2,
        }
      : null;

  // All visual styling lives on the outer View (NativeWind doesn't touch
  // static View styles). PressableScale handles the touch and carries only
  // transform + opacity, so there is nothing for NativeWind to strip.
  return (
    <View
      style={[
        {
          alignSelf: fullWidth ? 'stretch' : 'flex-start',
          backgroundColor: t.bg,
          borderColor: t.border,
          borderWidth: t.borderWidth,
          borderRadius: Radius.md,
          overflow: 'hidden',
        },
        shadow,
        style,
      ]}>
      <PressableScale
        onPress={onPress}
        disabled={isDisabled}
        accessibilityRole="button"
        accessibilityState={{ disabled: !!isDisabled, busy: !!loading }}
        {...rest}>
        <View
          style={[
            styles.row,
            {
              paddingVertical: s.paddingV,
              paddingHorizontal: s.paddingH,
              minHeight: s.minHeight,
            },
          ]}>
          {/* The label stays mounted while loading and the spinner sits on
              top of it. Swapping one for the other changed the button's
              intrinsic width, so buttons visibly resized under the thumb
              at the exact moment the user was waiting on them. */}
          <View style={[styles.row, { opacity: loading ? 0 : 1 }]}>
            {leadingIcon}
            <Text style={{ color: t.fg, fontFamily: Fonts.sansSemiBold, fontSize: s.font }}>
              {label}
            </Text>
            {trailingIcon}
          </View>
          {loading ? (
            <View style={StyleSheet.absoluteFill} pointerEvents="none">
              <View style={[styles.row, { flex: 1 }]}>
                <ActivityIndicator size="small" color={t.fg} />
              </View>
            </View>
          ) : null}
        </View>
      </PressableScale>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
});
