// ui/StatusPill — a status read-out: a small dot and a sentence-case label.
// tone: live | warn | muted | neutral. `pulse` animates the dot.
import { motion } from 'framer-motion'

const TONE = { live: 'badge-live', warn: 'badge-sim', muted: 'badge-mock', neutral: 'badge-connecting' }

export default function StatusPill({ tone = 'neutral', pulse = false, dot = true, className = '', children, ...rest }) {
  return (
    <span className={`gs-pill ${TONE[tone] ?? TONE.neutral} ${className}`} {...rest}>
      {dot && (pulse
        ? <motion.span className="gs-pill-dot" animate={{ opacity: [1, 0.35, 1] }} transition={{ duration: 1.6, repeat: Infinity }} aria-hidden="true" />
        : <span className="gs-pill-dot" aria-hidden="true" />)}
      {children}
    </span>
  )
}
