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
  // A step deeper than sage-mist. The mockup has one tint; the app needs
  // two, because a SELECTED option and a plain tinted panel sit side by side
  // (trial match tiers, chips, dashed tiles) and collapsing them to one hex
  // erases the distinction they exist to draw.
  primarySoft: '#D7E4D9',
  accent: '#E89260', // legacy urgent-calm accent; SOS pill only

  // Surfaces
  paper: '#F6F7F3', // --paper: the page ground
  surface: '#FFFFFF', // --card
  // A hair off paper, deliberately: Screen paints the ground with `paper`,
  // so a muted region set to the same hex has no edge at all.
  surfaceMuted: '#EFF2EC',
  sidebarBg: '#E4ECE5', // --sage-mist

  // The patient's own words — the ONLY warm element on screen.
  warmBubble: '#F1E9DC', // --warm
  warmBubbleBorder: '#E4D8C5',
  warmBubbleInk: '#5D4C36', // --warm-ink

  // Text — the ink scale
  textPrimary: '#24312B', // --ink
  textSecondary: '#5A6A61', // --ink-2
  // NOT the mockup's --ink-3 (#8A968E). That value is a placeholder and
  // disabled-glyph tint in the mockups; in this app textMuted carries real
  // content — list subtitles, timestamps, hints — at 12 and 13px, where
  // #8A968E measures 3.07:1 on white and 2.55:1 on the sage-mist rows in
  // the drawer. Darkened to clear WCAG AA (4.5:1) on every ground the app
  // actually paints. Hierarchy comes from size and weight instead of a
  // third value step.
  textMuted: '#5F6D64',

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

/**
 * Tracking (letter-spacing), which is SIZE-SPECIFIC and never one value.
 *
 * Letters read too far apart as type grows, so display sizes want negative
 * tracking; small uppercase labels want positive tracking or they set as a
 * solid block. A single fixed value is wrong somewhere by definition.
 *
 * This is not a new opinion: the approved mockups specify exactly this
 * (`letter-spacing:-0.01em` on the wordmark and page titles, `.04–.05em` on
 * the uppercase eyebrows) and the implementation dropped all of it. React
 * Native takes points rather than em, so these are the em values resolved
 * against the sizes they are used at.
 */
export const Tracking = {
  /** h1/h2 display type. About -0.01em at 24–28pt. */
  display: -0.3,
  /** Card and screen titles at 17–20pt. */
  title: -0.2,
  /** Body copy. Near zero, deliberately. */
  body: 0,
  /** Small uppercase labels and eyebrows. About +0.04em at 11–12pt. */
  eyebrow: 0.5,
} as const;

/**
 * Leading (line-height), which tracks size INVERSELY: tight on large
 * headings, looser on body copy.
 *
 * The app had 148 hardcoded line-heights across 12 distinct numbers. These
 * are multipliers, applied as `Math.round(size * Leading.x)`, so they stay
 * correct when the type scale moves.
 */
export const Leading = {
  /** Large display type. */
  tight: 1.2,
  /** Titles and short labels. */
  snug: 1.35,
  /** Body copy and anything read in quantity. */
  body: 1.5,
  /** Sage's own voice, which is read the longest and deserves the most air. */
  reading: 1.55,
} as const;

/** Resolve a leading multiplier against a size, rounded to whole points. */
export function leading(size: number, ratio: number = Leading.body): number {
  return Math.round(size * ratio);
}

export const Radius = {
  sm: 8,
  md: 12,
  lg: 18, // cards and bubbles (mockup: 18–20)
  xl: 20,
  pill: 999,
} as const;
