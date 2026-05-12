/**
 * WondrLink brand tokens.
 *
 * Mirrors public/index.html CSS custom properties so mobile and web stay
 * visually consistent. Light mode only (matches the recent web decision to
 * force light mode).
 */

export const Colors = {
  // Brand
  primary: '#1F5D4F',
  primaryLight: '#2A7869',
  accent: '#E89260',

  // Surfaces
  surface: '#FFFFFF',
  surfaceMuted: '#F7F7F5',
  sidebarBg: '#EDF2EF',

  // Text
  textPrimary: '#0F201C',
  textSecondary: '#475554',
  textMuted: '#6F7B7A',

  // System
  border: '#E1E4E1',
  danger: '#B3261E',
  warning: '#92400E',
  success: '#1F5D4F',

  // Status backgrounds
  warningBg: '#FEF3C7',
} as const;

export const Fonts = {
  sans: 'Geist_400Regular',
  sansMedium: 'Geist_500Medium',
  sansSemiBold: 'Geist_600SemiBold',
  sansBold: 'Geist_700Bold',
  serif: 'Fraunces_400Regular',
  serifBold: 'Fraunces_700Bold',
} as const;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  pill: 999,
} as const;
