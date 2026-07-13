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
  primaryPressed: '#17463B', // darker teal for button pressed/hover states
  // Soft brand tint used to highlight selected options (cards, pills, dropdown
  // rows). Distinctly teal — clearly differentiates the chosen option from
  // unselected ones while keeping `Colors.primary` text legible on top.
  primarySoft: '#CFE0D9',
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
  dangerPressed: '#8B1E18',
  warning: '#92400E',
  success: '#1F5D4F',

  // Status backgrounds
  warningBg: '#FEF3C7',
  emergencyBg: '#FFEDEC',
  dangerLight: '#FEE2E2',

  // SOS / Help pill (persistent top-bar affordance) — translucent accent so it
  // reads as urgent-but-calm. fg reuses `warning` (#92400E).
  sosBg: 'rgba(232,146,96,0.16)',
  sosBorder: 'rgba(232,146,96,0.45)',
  sosSolid: '#E89260',

  // Overlay scrim behind the drawer + bottom sheets.
  scrim: 'rgba(15,32,28,0.45)',
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

/**
 * Whole-number type scale. The app previously scattered ~25 fractional sizes
 * (10.5/12.5/13.5…) and 17 ad-hoc whole sizes; snap everything to this.
 *   xs 11  captions / eyebrows        lg 15  emphasized body / row titles
 *   sm 12  secondary / meta           xl 17  card + screen titles
 *   base 13 body-small                h3 20  section headings
 *   md 14  body / list rows           h2 24  page titles
 *                                     h1 28  Home greeting
 */
export const FontSize = {
  xs: 11,
  sm: 12,
  base: 13,
  md: 14,
  lg: 15,
  xl: 17,
  h3: 20,
  h2: 24,
  h1: 28,
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  pill: 999,
} as const;
