/**
 * Pill — a small rounded status label (DUE, "N saved", match band, etc.).
 * One radius, one type size — replaces ad-hoc inline badges.
 */

import { Text, View } from 'react-native';

import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';

type Tone = 'neutral' | 'brand' | 'accent' | 'danger';

const TONES: Record<Tone, { bg: string; fg: string }> = {
  neutral: { bg: Colors.sidebarBg, fg: Colors.textSecondary },
  brand: { bg: Colors.primarySoft, fg: Colors.primaryPressed },
  accent: { bg: Colors.sosBg, fg: Colors.warning },
  danger: { bg: Colors.dangerLight, fg: Colors.danger },
};

export function Pill({ tone = 'neutral', children }: { tone?: Tone; children: React.ReactNode }) {
  const c = TONES[tone];
  return (
    <View style={{ backgroundColor: c.bg, borderRadius: Radius.pill, paddingHorizontal: Spacing.sm, paddingVertical: 2 }}>
      <Text style={{ fontSize: FontSize.xs, fontFamily: Fonts.sansBold, color: c.fg, letterSpacing: 0.3 }}>{children}</Text>
    </View>
  );
}
