// [Windows] GraphSentinel
// constants/colors — every colour the app draws with, by name, in one place.
//
// Components used to carry these as hex literals: 658 of them across 32 files,
// 34 distinct values. Most are consumed where a Tailwind class cannot reach —
// Cytoscape and three.js styles, Recharts props, canvas fills, HTML built as a
// string, and inline styles that append an alpha suffix (`${color}40`) — so the
// single source is a JS module. tailwind.config.js imports it and exposes the
// same values as `gs-*` utilities, so a class and an inline style cannot drift.
//
// Values are exactly the ones the components already used. Two palettes are
// visible here (`danger` beside `threat`, `textSubtle` beside `textMuted`):
// merging them changes what the app looks like and is a design decision, not a
// refactor. It has not been made.

export const GS = {
  // ── text ──────────────────────────────────────────────────────────────────
  text: '#1b1f27',
  textMuted: '#5a616e',
  textSubtle: '#727a86',
  textFaint: '#9aa1ad',
  inkSoft: '#41474f',

  // ── surfaces and lines ────────────────────────────────────────────────────
  base: '#f4f6f8',
  surface: '#ffffff',
  surfaceRaised: '#f0f2f5',
  surfaceHeader: '#eef1f5',
  border: '#e2e5ea',
  borderStrong: '#c7cbd2',

  // ── semantic ──────────────────────────────────────────────────────────────
  danger: '#e03c3c',            // alerts, malicious, destructive actions
  dangerDeep: '#a32d2d',
  dangerOrange: '#c2410c',
  dangerBorderSoft: '#e03c3c25',
  dangerWash: '#e03c3c08',
  threat: '#d92d2d',            // the Tailwind `gs-threat` red
  warn: '#b7791f',
  success: '#12a672',
  successDeep: '#1d9e75',
  primary: '#3b56d9',
  primaryDeep: '#2c40a8',
  primaryGlow: '#4f6ef740',
  heal: '#5e5ce6',              // isolated / blocked
  chain: '#7c3aed',             // blockchain
  chainGlow: '#8b5cf660',

  // ── node status and attack types, as drawn on the graphs ──────────────────
  statusMalicious: '#e5484d',
  statusSuspicious: '#e8922a',
  attackPortScan: '#c99a0b',
  attackSshBrute: '#a16207',
  attackDosHulk: '#db2777',
  attackDosHulkLight: '#ec4899',
}

export default GS
