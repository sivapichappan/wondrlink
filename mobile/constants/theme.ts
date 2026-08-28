/**
 * Sage design tokens — "Paper and Lamplight" (approved 2026-08-28).
 *
 * Source of truth: docs/redesign/sage-mockups-v4.html.
 *
 * The paper foundation of the 2026-08-24 design, kept, with depth added and
 * the accent moved from sage green to ink blue. Three things carry the
 * character:
 *
 *   1. PAPER WITH SOMEWHERE FOR LIGHT TO FALL. The ground is a soft wash
 *      rather than a flat fill (see components/ui/Bloom.tsx), so the page
 *      recedes instead of sitting there.
 *   2. DEPTH INSTEAD OF OUTLINES. Cards lift on a real shadow rather than
 *      sitting behind a hairline. Elevation below is the scale.
 *   3. THE PATIENT'S OWN WORDS ARE THE ONE LIGHT IN THE ROOM. Kept verbatim
 *      from the approved design, which had it right; only the hue moved,
 *      warm beige to pale blue, so that one accent family serves both the
 *      day and night grounds.
 *
 * The night ground (#0C131C, lit from below) is defined in theme.night.ts
 * and is not wired up yet — see that file for what switching it on takes.
 *
 * Typography is semantic (it tells the patient who is speaking before they
 * read a word): Source Serif 4 is Sage's voice — chat messages, the
 * wordmark, the italic stage words, document titles. Instrument Sans is the
 * interface — buttons, chips, labels, and the patient's own bubbles.
 *
 * The previous approved palette is preserved verbatim in theme.v1.ts and at
 * the tag design-v1-approved-mockups; reverting is one `cp`.
 */

export const Colors = {
  // Brand — ink blue. The one change a returning user notices immediately.
  primary: '#24486B',
  primaryLight: '#3A6191',
  primaryPressed: '#1B3550', // deep ink: text on tints, pressed states
  primarySoft: '#CFDEEE', // selected fills, distinct from sidebarBg
  accent: '#E89260', // legacy urgent-calm accent; SOS pill only

  // Surfaces
  paper: '#F4F6F8', // the page ground; Bloom washes it lighter at the top
  surface: '#FFFFFF', // cards, which now lift rather than outline
  surfaceMuted: '#EDF0F3', // a hair off paper so muted regions still read
  sidebarBg: '#E4EDF7', // the blue tint: drawer rows, icon circles

  // The patient's own words — the one light in the room.
  warmBubble: '#E4EDF7',
  warmBubbleBorder: '#CFDEEE',
  warmBubbleInk: '#1B3550',

  // Text — the ink scale, now blue-black rather than green-black
  textPrimary: '#16202B',
  textSecondary: '#55636F',
  // Darkened from the mockup's muted value for the same reason as before:
  // this token carries real content at 12 and 13pt, and the lighter tint
  // fails AA on the grounds this app actually paints. 5.7:1 on paper.
  textMuted: '#55636F',

  // System
  border: '#DCE3EA',
  accentBorder: '#CFDEEE',
  danger: '#B3261E',
  dangerPressed: '#8B1E18',
  warning: '#92400E',
  success: '#24486B',

  // Status backgrounds
  warningBg: '#FEF3C7',
  emergencyBg: '#FFEDEC',
  dangerLight: '#FEE2E2',

  // SOS / Help pill. Deliberately OUTSIDE the blue family: it is the one
  // affordance that must not read as part of the calm palette.
  sosBg: 'rgba(232,146,96,0.16)',
  sosBorder: 'rgba(232,146,96,0.45)',
  sosSolid: '#E89260',

  // Overlay scrim behind the drawer + bottom sheets.
  scrim: 'rgba(16,32,43,0.45)',
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

/**
 * Elevation.
 *
 * The approved design separated everything with hairlines and carried no
 * shadow at all — a deliberate anti-vibecoded decision, and the right one
 * against a flat ground. "Paper and Lamplight" gives the page a light
 * source, and once light has a direction, things above the page cast
 * something.
 *
 * Two levels only, and both are soft and blue-tinted rather than grey: a
 * neutral drop shadow on a warm-blue paper reads as dirt. Anything that
 * needs more than `lifted` is probably a sheet and should be presented as
 * one.
 */
export const Elevation = {
  /** A card sitting on the page: dealt cards, list cards, the composer. */
  lifted: {
    shadowColor: '#16202B',
    shadowOpacity: 0.07,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  /** Something the user is acting on right now: a primary button. */
  active: {
    shadowColor: '#24486B',
    shadowOpacity: 0.22,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
  /** Explicitly flat. Named so a call site can say it MEANT no shadow. */
  flat: {
    shadowOpacity: 0,
    elevation: 0,
  },
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
