/**
 * Sage design tokens — the redesign palette (approved 2026-08-24).
 *
 * Source of truth: the `:root` block of docs/redesign/sage-mockups.html.
 * Green-tinted paper (deliberately not cream), sage actions, an ink scale
 * for text, and ONE warm element on screen: the patient's own words.
 *
 * Typography is semantic (it tells the patient who is speaking before they
 * read a word): Source Serif 4 is Sage's voice — chat messages, the
 * wordmark, the italic stage words, document titles. Instrument Sans is the
 * interface — buttons, chips, labels, and the patient's own bubbles.
 */

export const Colors = {
  // Brand — sage
  primary: '#4A7862', // --sage: the primary action color
  primaryLight: '#5D8A74', // derived hover/soft-emphasis tint
  primaryPressed: '#2F5443', // --sage-deep: pressed states, text on tints
  primarySoft: '#E4ECE5', // --sage-mist: selected/tinted fills
  accent: '#E89260', // legacy urgent-calm accent; SOS pill only

  // Surfaces
  paper: '#F6F7F3', // --paper: the page ground
  surface: '#FFFFFF', // --card
  surfaceMuted: '#F6F7F3', // muted fills align with paper
  sidebarBg: '#E4ECE5', // --sage-mist

  // The patient's own words — the ONLY warm element on screen.
  warmBubble: '#F1E9DC', // --warm
  warmBubbleBorder: '#E4D8C5',
  warmBubbleInk: '#5D4C36', // --warm-ink

  // Text — the ink scale
  textPrimary: '#24312B', // --ink
  textSecondary: '#5A6A61', // --ink-2
  textMuted: '#8A968E', // --ink-3

  // System
  border: '#E2E7E0', // --line: hairlines
  accentBorder: '#D5DFD6', // --sage-line: dealt cards, chips
  danger: '#B3261E',
  dangerPressed: '#8B1E18',
  warning: '#92400E',
  success: '#4A7862',

  // Status backgrounds
  warningBg: '#FEF3C7',
  emergencyBg: '#FFEDEC',
  dangerLight: '#FEE2E2',

  // SOS / Help pill (persistent top-bar affordance) — semantic crisis
  // affordance, deliberately outside the sage palette so it reads
  // urgent-but-calm. fg reuses `warning` (#92400E).
  sosBg: 'rgba(232,146,96,0.16)',
  sosBorder: 'rgba(232,146,96,0.45)',
  sosSolid: '#E89260',

  // Overlay scrim behind the drawer + bottom sheets (ink-based).
  scrim: 'rgba(36,49,43,0.45)',
} as const;

export const Fonts = {
  sans: 'InstrumentSans_400Regular',
  sansMedium: 'InstrumentSans_500Medium',
  sansSemiBold: 'InstrumentSans_600SemiBold',
  sansBold: 'InstrumentSans_700Bold',
  serif: 'SourceSerif4_400Regular',
  serifItalic: 'SourceSerif4_400Regular_Italic', // the stage words
  serifSemiBold: 'SourceSerif4_600SemiBold',
  serifBold: 'SourceSerif4_700Bold',
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
 * Sage's chat voice reads at 16 (serif, see MarkdownText) — between md and
 * lg by design; nothing patient-facing goes below 13.
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
  lg: 18, // cards and bubbles (mockup: 18–20)
  xl: 20,
  pill: 999,
} as const;
