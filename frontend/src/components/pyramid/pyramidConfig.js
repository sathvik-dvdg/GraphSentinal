// [Windows] GraphSentinel — Susheep
// pyramidConfig.js — static org hierarchy for PyramidHierarchy component

// ORG_HIERARCHY has been moved to api.js as a mock backend response.

// Level badge labels
import { GS } from '../../constants/colors'

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
  normal:     { border: 'rgba(43,42,40,0.12)', bg: 'transparent',          text: 'rgba(43,42,40,0.80)', badgeBg: 'transparent' },
  suspicious: { border: GS.warn,                bg: 'rgba(133,88,8,0.10)', text: GS.warn,               badgeBg: GS.warn },
  infected:   { border: GS.warn,                bg: 'rgba(133,88,8,0.10)', text: GS.warn,               badgeBg: GS.warn },
  malicious:  { border: GS.danger,                bg: 'rgba(180,19,46,0.10)',  text: GS.dangerOrange,               badgeBg: GS.danger },
  attacking:  { border: GS.danger,                bg: 'rgba(180,19,46,0.10)',  text: GS.dangerOrange,               badgeBg: GS.danger },
  isolated:   { border: GS.dangerDeep,                bg: 'rgba(127,15,32,0.15)', text: GS.danger,               badgeBg: GS.dangerDeep },
  blocked:    { border: GS.dangerDeep,                bg: 'rgba(127,15,32,0.10)', text: GS.danger,               badgeBg: GS.dangerDeep },
}
