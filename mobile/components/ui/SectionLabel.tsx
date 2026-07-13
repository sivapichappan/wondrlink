/**
 * SectionLabel — the uppercase eyebrow above a group ("RECENTS", "MY CARE").
 * One consistent size/weight/spacing everywhere.
 */

import { Text } from 'react-native';

import { Colors, FontSize, Fonts } from '@/constants/theme';

export function SectionLabel({ children, style }: { children: string; style?: object }) {
  return (
    <Text
      style={[
        { fontSize: FontSize.xs, fontFamily: Fonts.sansSemiBold, letterSpacing: 0.6, color: Colors.textMuted },
        style,
      ]}>
      {children.toUpperCase()}
    </Text>
  );
}
