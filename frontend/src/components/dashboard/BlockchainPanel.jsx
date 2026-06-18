// [Windows] GraphSentinel — Susheep
// ── All props and data bindings preserved verbatim ──
import { motion, AnimatePresence } from 'framer-motion'
import { Link2, Loader2 } from 'lucide-react'

export default function BlockchainPanel({ transactions }) {
  return (
    <div className="glass-card border-purple-500/15 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2.5 shrink-0 border-b border-outline-variant/30">
        <div className="flex items-center gap-2">
          <Link2 size={13} className="text-purple-400" />
          <span className="text-purple-400 font-mono text-xs font-bold tracking-widest uppercase">
            Blockchain Ledger
          </span>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-on-surface-variant text-[9px] font-mono tracking-wider">Ganache · Chain 1337</span>
          <span className="text-on-surface-variant/70 text-[9px] font-mono">Immutable Audit Trail</span>
        </div>
      </div>

      {/* Transaction list */}
      <div className="flex-1 overflow-auto p-2.5 space-y-2">
        <AnimatePresence initial={false}>
          {transactions.map((tx, i) => (
            <motion.div
              key={tx.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="relative rounded-lg overflow-hidden cursor-default transition-all duration-200 hover:brightness-110"
              style={{
                background: 'rgba(5, 20, 36, 0.45)',
                border: '1px solid rgba(168,85,247,0.15)',
                boxShadow: 'inset 0 1px 0 rgba(168,85,247,0.05)',
              }}
            >
              <div className="p-2.5">
                {/* TX Hash row */}
                <div className="flex items-center justify-between mb-2 gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    {/* Chain link icon + hash */}
                    <span className="text-purple-500/60 text-[10px] font-mono shrink-0">⛓</span>
                    <span className="text-purple-300 text-[10px] font-mono truncate">
                      {tx.tx_hash.slice(0, 16)}…{tx.tx_hash.slice(-6)}
                    </span>
                  </div>

                  {/* Status pill */}
                  {tx.status === 'confirmed' ? (
                    <span className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary-container/10 text-primary-container border border-primary-container/25 shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary-container" />
                      Immutable
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary-fixed/10 text-primary-fixed border border-primary-fixed/25 shrink-0">
                      <Loader2 size={9} className="spin-slow" />
                      Pending
                    </span>
                  )}
                </div>

                {/* Details row */}
                <div className="flex items-center gap-2 text-[10px] font-mono mb-2 flex-wrap">
                  <span className="text-error font-bold">{tx.attack_type}</span>
                  <span className="text-outline-variant/60">│</span>
                  <span className="text-on-surface">{tx.source_ip}</span>
                  <span className="text-outline-variant/60">│</span>
                  <span className="text-primary-fixed/70">#{tx.block_number}</span>
                </div>

                {/* Severity bar */}
                <div className="flex items-center gap-1.5 mb-1.5">
                  {Array.from({ length: 10 }, (_, j) => (
                    <div
                      key={j}
                      className="flex-1 h-1.5 rounded-sm transition-colors duration-300"
                      style={{
                        backgroundColor:
                          j < tx.severity
                            ? j < 6
                              ? '#fbbf2450'
                              : '#f43f5e80'
                            : 'rgba(119, 141, 169, 0.2)',
                      }}
                    />
                  ))}
                  <span className="text-on-surface-variant text-[9px] font-mono ml-1 shrink-0">
                    Sev {tx.severity}/10
                  </span>
                </div>

                {/* Gas used */}
                <div className="flex items-center justify-between text-[9px] font-mono text-on-surface-variant/70">
                  <span>Gas Used</span>
                  <span className="text-on-surface-variant tabular-nums">{tx.gas_used?.toLocaleString()}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Empty state */}
        {transactions.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="w-10 h-10 rounded-xl bg-purple-500/5 border border-purple-500/20 flex items-center justify-center mb-3">
              <Link2 size={18} className="text-purple-500/40" />
            </div>
            <p className="text-on-surface-variant text-xs font-mono">No blockchain records.</p>
            <p className="text-on-surface-variant/70 text-[10px] font-mono mt-1">
              Records appear when incidents are verified on-chain.
            </p>
          </div>
        )}
      </div>

      {/* Footer count */}
      {transactions.length > 0 && (
        <div className="px-3 py-2 border-t border-outline-variant/30 shrink-0">
          <div className="flex items-center justify-between">
            <span className="text-on-surface-variant/70 text-[10px] font-mono">
              {transactions.length} record{transactions.length !== 1 ? 's' : ''} on-chain
            </span>
            <div className="flex items-center gap-1">
              <div className="w-1 h-1 rounded-full bg-primary-container animate-pulse" />
              <span className="text-primary-container/60 text-[9px] font-mono">Ganache</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
