// [Windows] GraphSentinel — Susheep
// Theme constants — updated design system

// Node status colors — new semantic tokens
export const STATUS_COLORS = {
  normal:     '#8B8B8B',  // gs-normal gray
  suspicious: '#F5A623',  // gs-warn amber
  malicious:  '#FF453A',  // gs-threat red
  blocked:    '#5E5CE6',  // gs-heal indigo
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

// Attack type colors
export const ATTACK_COLORS = {
  DDoS:     '#FF453A',
  SSHBrute: '#F5A623',
  PortScan: '#E8CC2A',
  Botnet:   '#8B5CF6',
  DoSHulk:  '#EC4899',
  null:     '#2A2A2A',
}

// Severity styles — color + icon for accessibility
export const SEVERITY_STYLES = {
  critical: {
    border:    'border-gs-threat/40',
    badge:     'bg-gs-threat-soft text-gs-threat border-gs-threat/25',
    dot:       '#FF453A',
    icon:      '⬛',  // square — distinct shape
    label:     'CRITICAL',
    textColor: 'text-gs-threat',
  },
  warning: {
    border:    'border-gs-warn/30',
    badge:     'bg-gs-warn-soft text-gs-warn border-gs-warn/25',
    dot:       '#F5A623',
    icon:      '◆',  // diamond
    label:     'WARNING',
    textColor: 'text-gs-warn',
  },
  info: {
    border:    'border-gs-accent/20',
    badge:     'bg-gs-accent-soft text-gs-accent border-gs-accent/20',
    dot:       '#EAEAEA',
    icon:      '●',  // circle
    label:     'INFO',
    textColor: 'text-gs-accent',
  },
}

export const THEME = {
  base:      '#0A0A0A',
  surface:   '#141414',
  raised:    '#1E1E1E',
  border:    '#2A2A2A',
  accent:    '#EAEAEA',
  threat:    '#FF453A',
  warn:      '#F5A623',
  heal:      '#5E5CE6',
  chain:     '#8B5CF6',
  textPrimary: '#EAEAEA',
  textMuted:   '#8B8B8B',
  textFaint:   '#4D4D4D',
}
