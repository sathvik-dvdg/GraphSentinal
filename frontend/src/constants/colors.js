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
// The app wears the landing page's palette: a warm bone ground, charcoal ink and
// one crimson accent (which is also what marks a threat), with muted moss, ochre,
// slate and plum kept only where a status has to be told apart. Text colours were
// checked against the bone ground and the surface tint for WCAG contrast
// (textMuted 6.3:1, textSubtle 4.9:1, danger 5.5:1, warn and success above 4.5:1);
// textFaint is for placeholders and disabled text only.
// `danger` and `threat` are the same crimson and `primary` is ink, so the two
// older palettes this file used to carry are now one.

export const GS = {
  // ── text ──────────────────────────────────────────────────────────────────
  text: '#2b2a28',
  textMuted: '#55524d',
  textSubtle: '#66625b',
  textFaint: '#7d786f',
  inkSoft: '#413f3b',

  // ── surfaces and lines ────────────────────────────────────────────────────
  base: '#ebe7df',
  surface: '#f6f3ed',
  surfaceRaised: '#e3ded4',
  surfaceHeader: '#ddd8cd',
  border: '#d3cec3',
  borderStrong: '#b4aea1',

  // ── semantic ──────────────────────────────────────────────────────────────
  danger: '#b4132e',            // alerts, malicious, destructive actions: the landing crimson
  dangerDeep: '#7f0f20',
  dangerOrange: '#9a4a14',
  dangerBorderSoft: '#b4132e25',
  dangerWash: '#b4132e0a',
  threat: '#b4132e',            // the Tailwind `gs-threat` red (same crimson as `danger`)
  warn: '#855808',
  success: '#346348',
  successDeep: '#2c5640',
  primary: '#2b2a28',           // ink: links, active states, the quiet emphasis
  primaryDeep: '#1a1917',
  primaryGlow: '#2b2a2830',
  heal: '#4b5578',              // isolated / blocked
  chain: '#6b4a82',             // blockchain
  chainGlow: '#6b4a8260',

  // ── node status and attack types, as drawn on the graphs ──────────────────
  statusMalicious: '#b4132e',
  statusSuspicious: '#c27a1a',
  attackPortScan: '#7f6409',
  attackSshBrute: '#9a4a14',
  attackDosHulk: '#9b2c5a',
  attackDosHulkLight: '#b8527f',

  // Landing page: its own warm palette (pages/LandingPage, components/landing)
  landingBone: '#ebe7df',
  landingCharcoal: '#2b2a28',
  landingCrimson: '#b4132e',
}

export default GS
