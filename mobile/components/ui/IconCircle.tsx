/**
 * IconCircle — a circular icon chip. Replaces the six hand-computed `width/2`
 * radii scattered across screens; radius is always a true circle via Radius.pill.
 */

import { View } from 'react-native';

import { Colors, Radius } from '@/constants/theme';

export function IconCircle({
  size = 38,
  bg = Colors.sidebarBg,
  children,
}: {
  size?: number;
  bg?: string;
  children: React.ReactNode;
}) {
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: Radius.pill,
        backgroundColor: bg,
        alignItems: 'center',
        justifyContent: 'center',
      }}>
      {children}
    </View>
  );
}
