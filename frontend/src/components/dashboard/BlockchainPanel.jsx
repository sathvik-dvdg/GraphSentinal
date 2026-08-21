// [Windows] GraphSentinel — Susheep
// BlockchainPanel — redesigned with new token system
// ── All props and data bindings preserved verbatim ──
// § 4.6: blockchain_records: [] renders explicit empty state, not an error
import { motion, AnimatePresence } from 'framer-motion'
import { Link2, Loader2, CheckCircle } from 'lucide-react'
import CopyableHash from '../ui/CopyableHash'
import useGraphStore from '../../store/useGraphStore'

export default function BlockchainPanel({ transactions }) {
  const chainId = useGraphStore((s) => s.chainId)
  return (
    <div className="gs-panel border-gs-chain/15 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2.5 shrink-0 border-b border-gs-border">
        <div className="flex items-center gap-2">
          <Link2 size={13} className="text-gs-chain" aria-hidden="true" />
          <span className="text-gs-chain font-mono text-[11px] font-semibold tracking-widest uppercase">
            Blockchain Ledger
          </span>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-gs-muted text-[9px] font-mono">Ganache · Chain {chainId ?? '—'}</span>
          <span className="text-gs-faint text-[9px] font-mono">Immutable Audit Trail</span>
        </div>
      </div>

      {/* Transaction list */}
      <div className="flex-1 overflow-auto p-2 space-y-1.5" role="log" aria-label="Blockchain records">
        <AnimatePresence initial={false}>
          {transactions.map((tx, i) => (
            <motion.div
              key={tx.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="rounded-lg overflow-hidden cursor-default transition-all duration-150 hover:brightness-105"
              style={{
                background: '#1E1E1E',
                border: '1px solid rgba(139,92,246,0.15)',
              }}
            >
              <div className="p-2.5">
                {/* TX Hash row */}
                <div className="flex items-center justify-between mb-2 gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-gs-chain/60 text-[10px] font-mono shrink-0" aria-hidden="true">⛓</span>
                    <span className="text-gs-chain text-[10px] font-mono truncate tabular-nums">
                      <CopyableHash value={tx.tx_hash} prefixLen={16} suffixLen={4} iconSize={9} />
                    </span>
                  </div>

                  {/* Status pill — color + icon + text */}
                  {tx.status === 'confirmed' ? (
                    <span className="flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-gs-heal-soft text-gs-heal border border-gs-heal/20 shrink-0">
                      <CheckCircle size={8} aria-hidden="true" />
                      Confirmed
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-gs-warn-soft text-gs-warn border border-gs-warn/20 shrink-0">
                      <Loader2 size={8} className="spin-slow" aria-hidden="true" />
                      Pending
                    </span>
                  )}
                </div>

                {/* Details row */}
                <div className="flex items-center gap-2 text-[10px] font-mono mb-2 flex-wrap">
                  <span className="text-gs-threat font-semibold">{tx.attack_type}</span>
                  <span className="text-gs-faint">│</span>
                  <span className="text-gs-text tabular-nums">{tx.source_ip}</span>
                  <span className="text-gs-faint">│</span>
                  <span className="text-gs-muted tabular-nums">#{tx.block_number}</span>
                </div>

                {/* Severity bar — segmented */}
                <div className="flex items-center gap-0.5 mb-1.5" role="meter" aria-valuenow={tx.severity} aria-valuemin={0} aria-valuemax={10} aria-label={`Severity ${tx.severity}/10`}>
                  {Array.from({ length: 10 }, (_, j) => (
                    <div
                      key={j}
                      className="flex-1 rounded-sm"
                      style={{
                        height: 3,
                        backgroundColor:
                          j < tx.severity
                            ? j < 5 ? '#E8922A60' : '#E03C3C80'
                            : '#262D3F',
                      }}
                    />
                  ))}
                  <span className="text-gs-muted text-[9px] font-mono ml-1.5 shrink-0 tabular-nums">
                    {tx.severity}/10
                  </span>
                </div>

                {/* Gas used */}
                <div className="flex items-center justify-between text-[9px] font-mono text-gs-faint">
                  <span>Gas</span>
                  <span className="text-gs-muted tabular-nums">{tx.gas_used?.toLocaleString()}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* § 4.6: Explicit empty state — blockchain_records: [] is valid, not an error */}
        {transactions.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center" role="status">
            <div className="w-10 h-10 rounded-xl bg-gs-chain-soft border border-gs-chain/20 flex items-center justify-center mb-3">
              <Link2 size={18} className="text-gs-chain/40" aria-hidden="true" />
            </div>
            <p className="text-gs-muted text-[11px] font-mono">No blockchain records.</p>
            <p className="text-gs-faint text-[10px] font-mono mt-1">
              Records appear when incidents are verified on-chain.
            </p>
          </div>
        )}
      </div>

      {/* Footer count */}
      {transactions.length > 0 && (
        <div className="px-3 py-2 border-t border-gs-border shrink-0">
          <div className="flex items-center justify-between">
            <span className="text-gs-faint text-[10px] font-mono">
              {transactions.length} record{transactions.length !== 1 ? 's' : ''} on-chain
            </span>
            <div className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-gs-heal animate-pulse" aria-hidden="true" />
              <span className="text-gs-heal/60 text-[9px] font-mono">Ganache</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
