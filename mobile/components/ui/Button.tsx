import { ActivityIndicator, Pressable, Text, View, type PressableProps } from 'react-native';

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

  const colorsFor = (pressed: boolean) => {
    if (variant === 'primary') {
      return {
        bg: isDisabled ? Colors.border : pressed ? Colors.primaryLight : Colors.primary,
        fg: Colors.surface,
        border: 'transparent',
      };
    }
    if (variant === 'secondary') {
      return {
        bg: pressed ? Colors.sidebarBg : Colors.surface,
        fg: Colors.primary,
        border: Colors.primary,
      };
    }
    if (variant === 'danger') {
      return {
        bg: isDisabled ? Colors.border : pressed ? '#8B1E18' : Colors.danger,
        fg: Colors.surface,
        border: 'transparent',
      };
    }
    return { bg: 'transparent', fg: Colors.primary, border: 'transparent' };
  };

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!isDisabled, busy: !!loading }}
      style={({ pressed }) => {
        const c = colorsFor(pressed);
        return {
          backgroundColor: c.bg,
          borderColor: c.border,
          borderWidth: variant === 'secondary' ? 1 : 0,
          paddingVertical: s.paddingV,
          paddingHorizontal: s.paddingH,
          minHeight: s.minHeight,
          borderRadius: Radius.md,
          alignSelf: fullWidth ? 'stretch' : 'flex-start',
          opacity: isDisabled ? 0.6 : 1,
        };
      }}
      {...rest}>
      {({ pressed }) => {
        const c = colorsFor(pressed);
        return (
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            {loading ? (
              <ActivityIndicator size="small" color={c.fg} />
            ) : (
              <>
                {leadingIcon}
                <Text style={{ color: c.fg, fontFamily: Fonts.sansSemiBold, fontSize: s.font }}>{label}</Text>
                {trailingIcon}
              </>
            )}
          </View>
        );
      }}
    </Pressable>
  );
}
