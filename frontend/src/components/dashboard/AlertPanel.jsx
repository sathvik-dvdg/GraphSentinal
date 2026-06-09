// [Windows] GraphSentinel — Susheep
import { motion, AnimatePresence } from 'framer-motion'
import { SEVERITY_STYLES } from '../../constants/theme'

export default function AlertPanel({ alerts }) {
  return (
    <div className="bg-gs-card rounded-lg p-3 border border-gs-border h-full flex flex-col">
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h3 className="text-red-400 font-mono text-xs font-bold">🚨 THREAT FEED</h3>
        <span className="text-gray-600 text-xs font-mono">{alerts.length} events</span>
      </div>

      <div className="flex-1 overflow-auto space-y-1.5">
        <AnimatePresence initial={false}>
          {alerts.map((alert, i) => {
            const style = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.info
            return (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: 20, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3, delay: i * 0.03 }}
                className={`p-2 rounded border ${style.border} bg-gs-bg/50`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <motion.div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: style.dot }}
                    animate={
                      alert.severity === 'critical'
                        ? { scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }
                        : {}
                    }
                    transition={{ duration: 1.2, repeat: Infinity }}
                  />
                  <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${style.badge}`}>
                    {alert.attack_type}
                  </span>
                  <span className="text-gray-400 text-xs ml-auto font-mono">
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                <div className="text-gray-300 text-xs font-mono">{alert.source_ip}</div>

                {/* Threat bar */}
                <div className="mt-1 flex items-center gap-2">
                  <span className="text-gray-600 text-xs">Threat:</span>
                  <div className="flex-1 bg-gray-800 rounded-full h-1">
                    <motion.div
                      className="h-1 rounded-full"
                      style={{ backgroundColor: style.dot }}
                      initial={{ width: 0 }}
                      animate={{ width: `${alert.threat_score * 100}%` }}
                      transition={{ duration: 0.8, delay: i * 0.05 }}
                    />
                  </div>
                  <span className="text-xs font-mono" style={{ color: style.dot }}>
                    {(alert.threat_score * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Blockchain hash */}
                {alert.blockchain_tx && (
                  <div className="mt-1 text-purple-400 text-xs font-mono">
                    ⛓️ {alert.blockchain_tx.slice(0, 12)}...
                    <span className="text-green-400 ml-1">✓ on-chain</span>
                  </div>
                )}

                {alert.is_blocked && (
                  <div className="mt-1 text-blue-400 text-xs font-mono">🔒 Node isolated</div>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>

        {alerts.length === 0 && (
          <div className="text-gray-700 text-xs text-center py-4 font-mono">
            No threats detected.
          </div>
        )}
      </div>
    </div>
  )
}
