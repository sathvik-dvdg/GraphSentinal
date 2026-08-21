// [Windows] GraphSentinel — Susheep
// pyramidConfig.js — static org hierarchy for PyramidHierarchy component

// ORG_HIERARCHY has been moved to api.js as a mock backend response.

// Level badge labels
export const LEVEL_LABELS = {
  0: 'L0 · Root',
  1: 'L1 · Admin',
  2: 'L2 · Dept',
  3: 'L3 · Endpoint',
  4: 'L4 · Device',
}

// Node status styling map
// Covers both the UI-derived vocabulary (infected/attacking/isolated, built
// from alerts+healing events in useNodeHierarchy) and the backend's raw
// NodeStatus vocabulary (normal/suspicious/malicious/blocked), since
// graphData.node.status can flow in directly now that the hierarchy is
// built from live graph data (Error.md #2, #24) instead of a hardcoded tree.
export const STATUS_COLORS = {
  normal:     { border: 'rgba(255,255,255,0.12)', bg: 'transparent',          text: 'rgba(255,255,255,0.75)', badgeBg: 'transparent' },
  suspicious: { border: '#E8922A',                bg: 'rgba(232,146,42,0.10)', text: '#EF9F27',               badgeBg: '#E8922A' },
  infected:   { border: '#E8922A',                bg: 'rgba(232,146,42,0.10)', text: '#EF9F27',               badgeBg: '#E8922A' },
  malicious:  { border: '#E03C3C',                bg: 'rgba(224,60,60,0.10)',  text: '#F0997B',               badgeBg: '#E03C3C' },
  attacking:  { border: '#E03C3C',                bg: 'rgba(224,60,60,0.10)',  text: '#F0997B',               badgeBg: '#E03C3C' },
  isolated:   { border: '#A32D2D',                bg: 'rgba(163,45,45,0.15)', text: '#E03C3C',               badgeBg: '#A32D2D' },
  blocked:    { border: '#A32D2D',                bg: 'rgba(163,45,45,0.10)', text: '#E03C3C',               badgeBg: '#A32D2D' },
}
