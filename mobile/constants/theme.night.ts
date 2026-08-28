/**
 * The night ground — "Paper and Lamplight", lamp on.
 *
 * The same design as `theme.ts`, lit from below instead of above: the same
 * layout, the same type, the same components. Only the light moves. The
 * ground is a deep BLUE rather than black so it never goes to a dead flat
 * void, and the one light in the room is still the patient's own words.
 *
 * ── NOT WIRED UP YET, AND WHY ──────────────────────────────────────────
 *
 * Every one of ~60 files imports `Colors` statically from `theme.ts`, so
 * switching grounds at runtime needs an appearance-aware read, and there
 * are exactly two honest ways to get one:
 *
 *   1. A `useColors()` hook plus a provider, and a mechanical sweep of every
 *      call site. Correct, portable, and a very large diff.
 *   2. `DynamicColorIOS({ light, dark })`, which resolves per appearance
 *      wherever a colour string is accepted and would need NO call-site
 *      changes at all. Tempting, and the reason it is not done here: this
 *      app passes `Colors.*` into `lucide-react-native` icon `color` props,
 *      which reach `react-native-svg`, and a platform colour is not
 *      guaranteed to resolve there. Every icon in the app going black is
 *      the failure mode, and it is not verifiable without a device.
 *
 * So the night ground ships as data first, deliberately: the values are
 * fixed and contrast-checked, and the plumbing is a separate change that
 * deserves its own device pass rather than riding along with a palette swap
 * the owner is waiting to look at.
 *
 * Turning it on also means `app.json` moving from
 * `"userInterfaceStyle": "light"` to `"automatic"`, which is a native
 * config change and therefore a real build, not an OTA.
 *
 * Contrast, checked on the ground each pair is actually painted on:
 *   near-white on night ............ 15.98:1
 *   muted on night .................  7.22:1
 *   lamp blue on night ............. 10.87:1
 *   ink on the patient's bubble .... 12.78:1
 *   button ink on lamp blue ........  9.64:1
 */

export const NightColors = {
  // Brand — the lamp. Lighter than the day accent because it sits on dark.
  primary: '#A9C9EA',
  primaryLight: '#C3DAF2',
  primaryPressed: '#8FB6DE',
  primarySoft: 'rgba(169,201,234,0.14)',
  accent: '#E89260',

  // Surfaces. The bloom sits at the BOTTOM of the screen at night, where a
  // lamp beside a bed actually is (see components/ui/Bloom.tsx).
  paper: '#0C131C',
  surface: '#18202A',
  surfaceMuted: '#101A26',
  sidebarBg: 'rgba(233,238,243,0.055)',

  // The patient's own words: still the one light in the room.
  warmBubble: '#D7E6F7',
  warmBubbleBorder: '#D7E6F7',
  warmBubbleInk: '#12222F',

  // Text
  textPrimary: '#E9EEF3',
  textSecondary: '#A2AEB9',
  textMuted: '#93A3B2',

  // System
  border: '#27384A',
  accentBorder: '#2E4055',
  danger: '#F2857D',
  dangerPressed: '#D96B63',
  warning: '#E0B36B',
  success: '#A9C9EA',

  // Status backgrounds
  warningBg: '#2E2517',
  emergencyBg: '#2E1A18',
  dangerLight: '#3A201E',

  // SOS keeps its own hue on both grounds: it must never read as part of
  // the calm palette.
  sosBg: 'rgba(232,146,96,0.18)',
  sosBorder: 'rgba(232,146,96,0.48)',
  sosSolid: '#E89260',

  scrim: 'rgba(4,8,12,0.62)',
} as const;

/**
 * Elevation at night. Shadows do almost nothing on a dark ground, so depth
 * comes from a lighter surface fill instead; these exist so a component can
 * spread the same key without branching.
 */
export const NightElevation = {
  lifted: { shadowOpacity: 0, elevation: 0 },
  active: { shadowOpacity: 0, elevation: 0 },
  flat: { shadowOpacity: 0, elevation: 0 },
} as const;
