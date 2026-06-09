// [Windows] GraphSentinel — Susheep
import { motion, AnimatePresence } from 'framer-motion'

export default function SelfHealStatus({ events }) {
  return (
    <div className="bg-gs-card rounded-lg p-3 border border-gs-border h-full flex flex-col">
      <h3 className="text-blue-400 font-mono text-xs font-bold mb-2 shrink-0">
        🛡️ SELF-HEALING ENGINE
      </h3>

      <div className="flex-1 overflow-auto space-y-1.5">
        <AnimatePresence initial={false}>
          {events.map((event, i) => (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
              className="p-2 rounded border border-blue-500/20 bg-gs-bg/50"
            >
              {/* Row 1: Status transition */}
              <div className="flex items-center gap-2 mb-1">
                <motion.div
                  className="w-2.5 h-2.5 rounded-full"
                  animate={{ backgroundColor: ['#ff4444', '#0066ff'] }}
                  transition={{ duration: 1.5 }}
                />
                <span className="text-white text-xs font-mono font-bold">{event.ip}</span>
                <span className="text-gray-600 text-xs">→</span>
                <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">
                  {event.action}
                </span>
                <span className="text-gray-500 text-xs ml-auto font-mono">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
              </div>

              {/* Row 2: Details */}
              <div className="text-xs font-mono text-gray-400">
                Attack: <span className="text-red-400">{event.attack_type}</span> | Edges
                severed: {event.edges_severed} | {event.duration_ms}ms
              </div>

              {/* Row 3: Stability bar */}
              <div className="flex items-center gap-2 mt-1.5">
                <span className="text-gray-600 text-xs">Stability:</span>
                <div className="flex-1 bg-gray-800 rounded-full h-1.5 relative overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-gs-accent"
                    initial={{ width: `${event.network_stability_before}%` }}
                    animate={{ width: `${event.network_stability_after}%` }}
                    transition={{ duration: 1.5, ease: 'easeOut' }}
                  />
                </div>
                <span className="text-gs-accent text-xs font-mono">
                  {event.network_stability_before}% → {event.network_stability_after}%
                </span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {events.length === 0 && (
          <div className="text-gray-700 text-xs text-center py-4 font-mono">
            No healing events.
          </div>
        )}
      </div>
    </div>
  )
}
