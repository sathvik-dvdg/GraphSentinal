// [Windows] GraphSentinel — Susheep
import { motion, AnimatePresence } from 'framer-motion'

export default function BlockchainPanel({ transactions }) {
  return (
    <div className="bg-gs-card rounded-lg p-3 border border-gs-border h-full flex flex-col">
      {/* Header — title and subtitle on separate lines to prevent overlap */}
      <div className="mb-2 shrink-0">
        <h3 className="text-purple-400 font-mono text-xs font-bold">⛓️ BLOCKCHAIN LEDGER</h3>
        <span className="text-gray-600 text-[10px] font-mono">Ganache · Chain 1337 · Immutable Audit Trail</span>
      </div>

      <div className="flex-1 overflow-auto space-y-1.5">
        <AnimatePresence initial={false}>
          {transactions.map((tx, i) => (
            <motion.div
              key={tx.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="p-2 rounded border border-purple-500/20 bg-gs-bg/50"
            >
              {/* TX Hash */}
              <div className="flex items-center justify-between mb-1">
                <span className="text-purple-400 text-xs font-mono truncate max-w-[180px]">
                  {tx.tx_hash.slice(0, 18)}...{tx.tx_hash.slice(-6)}
                </span>
                <span
                  className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                    tx.status === 'confirmed'
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-yellow-500/20 text-yellow-400'
                  }`}
                >
                  {tx.status === 'confirmed' ? '✓ Immutable' : '⏳ Pending'}
                </span>
              </div>

              {/* Details row */}
              <div className="flex items-center gap-2 text-xs font-mono text-gray-400">
                <span className="text-red-400">{tx.attack_type}</span>
                <span className="text-gray-600">|</span>
                <span>{tx.source_ip}</span>
                <span className="text-gray-600">|</span>
                <span>Block #{tx.block_number}</span>
              </div>

              {/* Severity bar */}
              <div className="flex items-center gap-1 mt-1.5">
                {Array.from({ length: 10 }, (_, j) => (
                  <div
                    key={j}
                    className="w-2 h-2 rounded-sm"
                    style={{
                      backgroundColor: j < tx.severity ? '#ff4444' : '#1f2937',
                    }}
                  />
                ))}
                <span className="text-gray-600 text-xs ml-1 font-mono">{tx.gas_used} gas</span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {transactions.length === 0 && (
          <div className="text-center py-6">
            <div className="text-gray-700 text-2xl mb-2">⛓️</div>
            <div className="text-gray-600 text-xs font-mono">No blockchain records yet.</div>
            <div className="text-gray-700 text-[10px] font-mono mt-1">
              Records appear when incidents are verified on-chain.
            </div>
          </div>
        )}
      </div>

      {transactions.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gs-border text-center shrink-0">
          <span className="text-gray-600 text-xs font-mono">
            {transactions.length} record{transactions.length !== 1 ? 's' : ''} on-chain
          </span>
        </div>
      )}
    </div>
  )
}
