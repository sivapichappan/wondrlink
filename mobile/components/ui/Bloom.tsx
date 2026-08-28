/**
 * Bloom — the page's light source.
 *
 * "Paper and Lamplight" replaces a flat fill with a soft wash, so the ground
 * has somewhere to fall away to. It is the difference between a screen that
 * is a colour and one that is a surface, and it costs nothing at runtime: a
 * single static SVG gradient behind everything, no animation, no blur, no
 * per-frame work.
 *
 * react-native-svg rather than a gradient library, because it is already a
 * dependency (the Sparkline uses it) and adding a package here would mean a
 * lockfile churn, which is what broke EAS bundling once before.
 *
 * By day the light comes from the TOP, the way daylight enters a room. The
 * night ground reverses it — the lamp is beside the bed, below the screen —
 * which is why the direction is a prop rather than a constant.
 */

import { StyleSheet, View } from 'react-native';
import Svg, { Defs, RadialGradient, Rect, Stop } from 'react-native-svg';

import { Colors } from '@/constants/theme';

interface Props {
  /** Where the light comes from. Day: above. Night: the lamp, below. */
  from?: 'above' | 'below';
  children?: React.ReactNode;
}

export function Bloom({ from = 'above', children }: Props) {
  const cy = from === 'above' ? '-6%' : '106%';

  return (
    <View style={{ flex: 1, backgroundColor: Colors.paper }}>
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        <Svg width="100%" height="100%">
          <Defs>
            <RadialGradient id="bloom" cx="50%" cy={cy} rx="115%" ry="48%">
              <Stop offset="0%" stopColor={Colors.surface} stopOpacity="1" />
              <Stop offset="55%" stopColor={Colors.paper} stopOpacity="1" />
              <Stop offset="100%" stopColor={Colors.surfaceMuted} stopOpacity="1" />
            </RadialGradient>
          </Defs>
          <Rect x="0" y="0" width="100%" height="100%" fill="url(#bloom)" />
        </Svg>
      </View>
      {children}
    </View>
  );
}
