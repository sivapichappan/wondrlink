import { Check } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

interface Props {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}

export function Checkbox({ checked, onChange, label, description, disabled }: Props) {
  return (
    <Pressable
      onPress={() => !disabled && onChange(!checked)}
      disabled={disabled}
      accessibilityRole="checkbox"
      accessibilityState={{ checked, disabled: !!disabled }}
      style={({ pressed }) => ({
        opacity: pressed && !disabled ? 0.85 : 1,
      })}>
      {/* Layout lives on a static inner View — NativeWind strips
          flexDirection/gap from Pressable style FUNCTIONS, which rendered
          the box and its label on separate lines. */}
      <View style={{ flexDirection: 'row', gap: 12, paddingVertical: 10 }}>
      <View
        style={{
          width: 22,
          height: 22,
          borderRadius: Radius.sm,
          borderWidth: 1.5,
          borderColor: disabled
            ? Colors.border
            : checked
              ? Colors.primary
              : Colors.border,
          backgroundColor: disabled
            ? Colors.surfaceMuted
            : checked
              ? Colors.primary
              : Colors.surface,
          alignItems: 'center',
          justifyContent: 'center',
          marginTop: 2,
        }}>
        {checked && <Check size={16} color={Colors.surface} strokeWidth={3} />}
      </View>
      <View style={{ flex: 1, gap: 4 }}>
        <Text
          style={{
            color: disabled ? Colors.textMuted : Colors.textPrimary,
            fontFamily: Fonts.sansMedium,
            fontSize: 14,
            lineHeight: 20,
          }}>
          {label}
        </Text>
        {description && (
          <Text
            style={{
              color: disabled ? Colors.textMuted : Colors.textSecondary,
              fontSize: 13,
              lineHeight: 19,
            }}>
            {description}
          </Text>
        )}
      </View>
      </View>
    </Pressable>
  );
}
