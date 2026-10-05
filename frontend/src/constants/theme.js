// [Windows] GraphSentinel — Susheep
// Theme constants — clean white design system

// Node status colors — tuned for filled shapes on a white canvas
import { GS } from './colors'

export const STATUS_COLORS = {
  normal:     GS.textFaint,  // neutral gray
  suspicious: GS.statusSuspicious,  // amber
  malicious:  GS.statusMalicious,  // red
  blocked:    GS.heal,  // indigo
}

// Node status icons/shapes — used alongside color for accessibility
export const STATUS_ICONS = {
  normal:     '●',  // filled circle
  suspicious: '◆',  // filled diamond
  malicious:  '▲',  // filled triangle (warning shape)
  blocked:    '⬡',  // hexagon (cage/containment)
}

export const STATUS_LABELS = {
  normal:     'Normal',
  suspicious: 'Suspicious',
  malicious:  'Malicious',
  blocked:    'Blocked',
}

// Attack type colors — 'null' is the no-attack baseline link color (light gray on white)
export const ATTACK_COLORS = {
  DDoS:     GS.statusMalicious,
  SSHBrute: GS.statusSuspicious,
  PortScan: GS.attackPortScan,
  Botnet:   GS.chain,
  DoSHulk:  GS.attackDosHulk,
  null:     GS.borderStrong,
}

// Severity styles — color + icon for accessibility
export const SEVERITY_STYLES = {
  critical: {
    border:    'border-gs-threat/40',
    badge:     'bg-gs-threat-soft text-gs-threat border-gs-threat/25',
    dot:       GS.threat,
    icon:      '⬛',  // square — distinct shape
    label:     'CRITICAL',
    textColor: 'text-gs-threat',
  },
  warning: {
    border:    'border-gs-warn/30',
    badge:     'bg-gs-warn-soft text-gs-warn border-gs-warn/25',
    dot:       GS.warn,
    icon:      '◆',  // diamond
    label:     'WARNING',
    textColor: 'text-gs-warn',
  },
  info: {
    border:    'border-gs-accent/20',
    badge:     'bg-gs-accent-soft text-gs-accent border-gs-accent/20',
    dot:       GS.textMuted,
    icon:      '●',  // circle
    label:     'INFO',
    textColor: 'text-gs-accent',
  },
}

export const THEME = {
  base:      GS.base,
  surface:   GS.surface,
  raised:    GS.surfaceRaised,
  border:    GS.border,
  accent:    GS.text,
  threat:    GS.threat,
  warn:      GS.warn,
  heal:      GS.heal,
  chain:     GS.chain,
  textPrimary: GS.text,
  textMuted:   GS.textMuted,
  textFaint:   GS.textFaint,
}
