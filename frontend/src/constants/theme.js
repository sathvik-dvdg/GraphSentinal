// [Windows] GraphSentinel — Susheep
// Theme constants — frozen design system

export const STATUS_COLORS = {
  normal: '#00ff88',
  suspicious: '#ffaa00',
  malicious: '#ff4444',
  blocked: '#0066ff',
}

export const ATTACK_COLORS = {
  DDoS: '#ff4444',
  SSHBrute: '#ff8800',
  PortScan: '#ffff00',
  Botnet: '#aa44ff',
  DoSHulk: '#ff2266',
  null: '#1e3a5f',
}

export const SEVERITY_STYLES = {
  critical: {
    border: 'border-red-500/40',
    badge: 'bg-red-500/20 text-red-400',
    dot: '#ff4444',
  },
  warning: {
    border: 'border-yellow-500/30',
    badge: 'bg-yellow-500/20 text-yellow-400',
    dot: '#ffaa00',
  },
  info: {
    border: 'border-blue-500/20',
    badge: 'bg-blue-500/20 text-blue-400',
    dot: '#0099ff',
  },
}

export const THEME = {
  bg: '#0a0e1a',
  card: '#111827',
  mid: '#0d1424',
  accent: '#00ff88',
  alert: '#ff4444',
  warn: '#ffaa00',
  info: '#0066ff',
  chain: '#9945ff',
  border: '#1f2937',
  textPrimary: '#e2e8f0',
  textMuted: '#6b7280',
  textFaint: '#374151',
}
