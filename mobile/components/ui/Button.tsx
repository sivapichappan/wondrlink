import { ActivityIndicator, Pressable, StyleSheet, Text, View, type PressableProps } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

interface Props extends Omit<PressableProps, 'children'> {
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
  // static View styles). The Pressable inside only handles tap + an opacity
  // dim for press feedback — its style function can stay simple.
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
      ]}>
      <Pressable
        onPress={onPress}
        disabled={isDisabled}
        accessibilityRole="button"
        accessibilityState={{ disabled: !!isDisabled, busy: !!loading }}
        style={({ pressed }) => ({
          opacity: pressed && !isDisabled ? 0.85 : 1,
        })}
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
          {loading ? (
            <ActivityIndicator size="small" color={t.fg} />
          ) : (
            <>
              {leadingIcon}
              <Text style={{ color: t.fg, fontFamily: Fonts.sansSemiBold, fontSize: s.font }}>
                {label}
              </Text>
              {trailingIcon}
            </>
          )}
        </View>
      </Pressable>
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
