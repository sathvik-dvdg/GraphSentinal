// [Windows] GraphSentinel — Susheep
// SelfHealStatus — redesigned with new token system
// ── All props and data bindings preserved verbatim ──
import { motion, AnimatePresence } from 'framer-motion'
import { Cpu, ShieldCheck } from 'lucide-react'
import { formatEventTimestamp } from '../../utils/formatTimestamp'

export default function SelfHealStatus({ events }) {
  return (
    <div className="gs-panel border-gs-heal/15 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2.5 shrink-0 border-b border-gs-border">
        <div className="flex items-center gap-2">
          <Cpu size={13} className="text-gs-heal" aria-hidden="true" />
          <span className="text-gs-heal font-mono text-[11px] font-semibold tracking-widest uppercase">
            Self-Healing Engine
          </span>
        </div>
        <span className="text-gs-muted text-[9px] font-mono">
          {events.length} event{events.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Event list */}
      <div className="flex-1 overflow-auto p-2 space-y-1.5" role="log" aria-label="Self-healing events">
        <AnimatePresence initial={false}>
          {events.map((event) => (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -16 }}
              transition={{ duration: 0.25 }}
              className="rounded-lg overflow-hidden cursor-default"
              style={{
                background: '#1E1E1E',
                border: '1px solid rgba(46,204,138,0.12)',
                borderLeft: '2px solid rgba(46,204,138,0.45)',
              }}
            >
              <div className="p-2.5">
                {/* Row 1: IP + action badge + time */}
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  {/* Healing status dot — animated color transition */}
                  <motion.div
                    className="w-2 h-2 rounded-full shrink-0"
                    animate={{ backgroundColor: ['#E03C3C', '#4F6EF7', '#2ECC8A'] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    aria-hidden="true"
                  />
                  <span className="text-gs-text text-[11px] font-mono font-semibold tabular-nums">
                    {event.ip}
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-gs-heal-soft text-gs-heal border border-gs-heal/20">
                    {event.action}
                  </span>
                  <span className="text-gs-muted text-[9px] ml-auto font-mono tabular-nums shrink-0">
                    {formatEventTimestamp(event.timestamp)}
                  </span>
                </div>

                {/* Row 2: detail chips */}
                <div className="flex items-center gap-2 flex-wrap mb-2 text-[10px] font-mono">
                  <span className="px-1.5 py-0.5 rounded-md bg-gs-threat-soft text-gs-threat border border-gs-threat/20">
                    {event.attack_type}
                  </span>
                  <span className="text-gs-faint">·</span>
                  <span className="text-gs-muted">{event.edges_severed} edges cut</span>
                  <span className="text-gs-faint">·</span>
                  <span className="text-gs-accent tabular-nums">{event.duration_ms}ms</span>
                </div>

                {/* Row 3: Network stability recovery bar */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[9px] font-mono">
                    <span className="text-gs-muted uppercase tracking-wider">Network Stability</span>
                    <span className="text-gs-heal font-semibold tabular-nums">
                      {event.network_stability_before}% → {event.network_stability_after}%
                    </span>
                  </div>
                  <div
                    className="relative rounded-full overflow-hidden"
                    style={{ height: 3, background: '#262D3F' }}
                    role="progressbar"
                    aria-valuenow={event.network_stability_after}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Network stability improved from ${event.network_stability_before}% to ${event.network_stability_after}%`}
                  >
                    {/* Before marker */}
                    <div
                      className="absolute top-0 h-full rounded-full"
                      style={{
                        width: `${event.network_stability_before}%`,
                        backgroundColor: '#E8922A30',
                      }}
                    />
                    {/* After recovery bar */}
                    <motion.div
                      className="absolute top-0 h-full rounded-full motion-functional"
                      style={{ background: 'linear-gradient(90deg, #4F6EF7, #2ECC8A)' }}
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
          <div className="flex flex-col items-center justify-center py-8 text-center" role="status">
            <div className="relative w-10 h-10 mb-3">
              <div className="absolute inset-0 rounded-xl bg-gs-heal-soft border border-gs-heal/20" />
              <ShieldCheck
                size={18}
                className="text-gs-heal/50 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
                aria-hidden="true"
              />
            </div>
            <p className="text-gs-muted text-[11px] font-mono">No healing events.</p>
            <p className="text-gs-faint text-[10px] font-mono mt-1">
              Malicious nodes are auto-isolated here.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
