// [Windows] GraphSentinel
// HostStateIcon -- the icon each host state carries beside its word, so a state
// never rests on colour alone. One icon family (lucide), one stroke width.
import { CheckCircle2, Eye, Lock, TriangleAlert } from 'lucide-react'

const ICONS = { healthy: CheckCircle2, watching: Eye, contained: Lock, threat: TriangleAlert }

export default function HostStateIcon({ state, size = 16 }) {
  const Icon = ICONS[state] || Eye
  return <Icon size={size} strokeWidth={2} aria-hidden="true" style={{ flexShrink: 0 }} />
}
