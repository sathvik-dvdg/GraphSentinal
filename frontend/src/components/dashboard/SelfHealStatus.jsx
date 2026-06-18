// [Windows] GraphSentinel — Susheep
// ── All props and data bindings preserved verbatim ──
import { motion, AnimatePresence } from 'framer-motion'
import { Cpu } from 'lucide-react'

export default function SelfHealStatus({ events }) {
  return (
    <div className="glass-card border-primary-container/15 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2.5 shrink-0 border-b border-outline-variant/30">
        <div className="flex items-center gap-2">
          <Cpu size={13} className="text-primary-container" />
          <span className="text-primary-container font-mono text-xs font-bold tracking-widest uppercase">
            Self-Healing Engine
          </span>
        </div>
        <span className="text-on-surface-variant text-[9px] font-mono tracking-wider">
          {events.length} event{events.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Event list */}
      <div className="flex-1 overflow-auto p-2.5 space-y-2">
        <AnimatePresence initial={false}>
          {events.map((event) => (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
              className="relative rounded-lg overflow-hidden cursor-default transition-all duration-200 hover:brightness-110"
              style={{
                background: 'rgba(5, 20, 36, 0.45)',
                border: '1px solid rgba(0, 219, 231, 0.12)',
                borderLeft: '2px solid rgba(0, 219, 231, 0.5)',
              }}
            >
              <div className="p-2.5">
                {/* Row 1: IP + action badge + time */}
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  {/* Animated status dot (original animate values preserved) */}
                  <motion.div
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    animate={{ backgroundColor: ['#f43f5e', '#06b6d4', '#34d399'] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                  <span className="text-white text-xs font-mono font-bold">{event.ip}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary-container/10 text-primary-container border border-primary-container/25">
                    {event.action}
                  </span>
                  <span className="text-on-surface-variant text-[9px] ml-auto font-mono tabular-nums shrink-0">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                {/* Row 2: details chips */}
                <div className="flex items-center gap-2 flex-wrap mb-2.5 text-[10px] font-mono">
                  <span className="px-1.5 py-0.5 rounded bg-error/10 text-error border border-error/20">
                    {event.attack_type}
                  </span>
                  <span className="text-on-surface-variant">·</span>
                  <span className="text-on-surface-variant/70">
                    {event.edges_severed} edges cut
                  </span>
                  <span className="text-on-surface-variant">·</span>
                  <span className="text-primary-fixed/80">{event.duration_ms}ms</span>
                </div>

                {/* Row 3: Stability recovery bar */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[9px] font-mono">
                    <span className="text-on-surface-variant uppercase tracking-wider">Network Stability</span>
                    <span className="text-primary-container font-bold">
                      {event.network_stability_before}% → {event.network_stability_after}%
                    </span>
                  </div>
                  <div className="relative h-2 bg-outline-variant/30 rounded-full overflow-hidden">
                    {/* Before marker */}
                    <div
                      className="absolute top-0 h-full bg-amber-500/20 rounded-full"
                      style={{ width: `${event.network_stability_before}%` }}
                    />
                    {/* After recovery bar (animated — original values preserved) */}
                    <motion.div
                      className="absolute top-0 h-full rounded-full"
                      style={{
                        background: 'linear-gradient(90deg, #06b6d4, #34d399)',
                        boxShadow: '0 0 8px rgba(52,211,153,0.4)',
                      }}
                      initial={{ width: `${event.network_stability_before}%` }}
                      animate={{ width: `${event.network_stability_after}%` }}
                      transition={{ duration: 1.5, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Empty state */}
        {events.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="relative w-10 h-10 mb-3">
              <div className="absolute inset-0 rounded-xl bg-primary-container/5 border border-primary-container/20" />
              <Cpu size={18} className="text-primary-container/40 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            </div>
            <p className="text-on-surface-variant text-xs font-mono">No healing events.</p>
            <p className="text-on-surface-variant/70 text-[10px] font-mono mt-1">
              Malicious nodes are auto-isolated here.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
