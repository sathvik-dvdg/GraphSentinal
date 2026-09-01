// [Windows] GraphSentinel — Susheep
// Theme constants — clean white design system

// Node status colors — tuned for filled shapes on a white canvas
export const STATUS_COLORS = {
  normal:     '#9AA1AD',  // neutral gray
  suspicious: '#E8922A',  // amber
  malicious:  '#E5484D',  // red
  blocked:    '#5E5CE6',  // indigo
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
  DDoS:     '#E5484D',
  SSHBrute: '#E8922A',
  PortScan: '#C99A0B',
  Botnet:   '#7C3AED',
  DoSHulk:  '#DB2777',
  null:     '#C7CBD2',
}

// Severity styles — color + icon for accessibility
export const SEVERITY_STYLES = {
  critical: {
    border:    'border-gs-threat/40',
    badge:     'bg-gs-threat-soft text-gs-threat border-gs-threat/25',
    dot:       '#D92D2D',
    icon:      '⬛',  // square — distinct shape
    label:     'CRITICAL',
    textColor: 'text-gs-threat',
  },
  warning: {
    border:    'border-gs-warn/30',
    badge:     'bg-gs-warn-soft text-gs-warn border-gs-warn/25',
    dot:       '#B7791F',
    icon:      '◆',  // diamond
    label:     'WARNING',
    textColor: 'text-gs-warn',
  },
  info: {
    border:    'border-gs-accent/20',
    badge:     'bg-gs-accent-soft text-gs-accent border-gs-accent/20',
    dot:       '#5A616E',
    icon:      '●',  // circle
    label:     'INFO',
    textColor: 'text-gs-accent',
  },
}

export const THEME = {
  base:      '#F4F6F8',
  surface:   '#FFFFFF',
  raised:    '#F0F2F5',
  border:    '#E2E5EA',
  accent:    '#1B1F27',
  threat:    '#D92D2D',
  warn:      '#B7791F',
  heal:      '#5E5CE6',
  chain:     '#7C3AED',
  textPrimary: '#1B1F27',
  textMuted:   '#5A616E',
  textFaint:   '#9AA1AD',
}
