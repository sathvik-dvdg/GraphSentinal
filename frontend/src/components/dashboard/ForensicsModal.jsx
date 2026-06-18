// [Windows] GraphSentinel — Susheep
// ── ALL state, effects, data bindings, and handlers preserved verbatim ──
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, RefreshCw, Search, Link2 } from 'lucide-react'
import { getForensics } from '../../services/api'

export default function ForensicsModal({ isOpen, onClose }) {
  // ── Original state — untouched ──
  const [tab, setTab] = useState('incidents')
  const [data, setData] = useState({
    incidents: [],
    blockchain_records: [],
    total_incidents: 0,
    total_on_chain: 0,
    contract_address: null,
  })
  const [loading, setLoading] = useState(false)

  // ── Original refresh + effect — untouched ──
  const refresh = () => {
    setLoading(true)
    getForensics()
      .then((res) => setData(res))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (isOpen) {
      refresh()
      const interval = setInterval(refresh, 3000)
      return () => clearInterval(interval)
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <AnimatePresence>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center"
        style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(4px)' }}
        onClick={onClose}
      >
        {/* Modal panel */}
        <motion.div
          initial={{ scale: 0.92, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.92, opacity: 0, y: 20 }}
          transition={{ type: 'spring', damping: 22 }}
          className="w-[90vw] max-w-4xl max-h-[82vh] overflow-hidden flex flex-col rounded-2xl"
          style={{
            background: 'rgba(9,14,31,0.97)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(30,41,59,0.8)',
            boxShadow: '0 0 0 1px rgba(6,182,212,0.06), 0 40px 80px rgba(0,0,0,0.8)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Top accent line */}
          <div className="h-px w-full bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent shrink-0" />

          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800/60 shrink-0">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Search size={15} className="text-cyan-400" />
                <h2 className="font-orbitron text-sm font-bold text-white tracking-widest uppercase">
                  Forensics Report
                </h2>
              </div>

              {data.contract_address && (
                <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-purple-500/20 bg-purple-500/5">
                  <Link2 size={10} className="text-purple-400" />
                  <span className="text-[10px] text-purple-400 font-mono">
                    {data.contract_address.slice(0, 10)}…
                  </span>
                </div>
              )}

              <span className="text-[10px] text-slate-600 font-mono">Chain ID: 1337</span>

              {loading && (
                <div className="flex items-center gap-1.5">
                  <RefreshCw size={10} className="text-cyan-400 spin-slow" />
                  <span className="text-[10px] text-cyan-400 font-mono animate-pulse">SYNCING</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* Refresh button — onClick original handler preserved */}
              <button
                onClick={refresh}
                className="tac-btn flex items-center gap-1.5 text-slate-400 hover:text-cyan-400 border border-slate-700 hover:border-cyan-500/40 hover:bg-cyan-500/5 text-[10px] font-mono px-3 py-1.5 rounded-lg transition-all duration-200"
              >
                <RefreshCw size={10} />
                REFRESH
              </button>
              {/* Close button — onClick original handler preserved */}
              <button
                onClick={onClose}
                className="w-7 h-7 flex items-center justify-center rounded-lg border border-slate-800 text-slate-500 hover:text-white hover:border-slate-600 transition-all duration-200"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Stat summary row */}
          <div className="flex items-center gap-0 border-b border-slate-800/60 shrink-0">
            <div className="flex items-center gap-3 px-5 py-2 border-r border-slate-800/60">
              <span className="text-xs font-bold text-white font-mono tabular-nums">{data.total_incidents}</span>
              <span className="text-[10px] text-slate-600 font-mono uppercase tracking-wider">Total Incidents</span>
            </div>
            <div className="flex items-center gap-3 px-5 py-2">
              <span className="text-xs font-bold text-emerald-400 font-mono tabular-nums">{data.total_on_chain}</span>
              <span className="text-[10px] text-slate-600 font-mono uppercase tracking-wider">On-Chain Records</span>
            </div>
          </div>

          {/* Tabs — original onClick setTab preserved */}
          <div className="flex items-center gap-0 border-b border-slate-800/60 px-5 shrink-0">
            <TabBtn
              label={`INCIDENTS (${data.total_incidents})`}
              active={tab === 'incidents'}
              color="cyan"
              onClick={() => setTab('incidents')}
            />
            <TabBtn
              label={`BLOCKCHAIN (${data.total_on_chain})`}
              active={tab === 'blockchain'}
              color="purple"
              onClick={() => setTab('blockchain')}
            />
          </div>

          {/* Table content — all original data binding keys preserved */}
          <div className="flex-1 overflow-auto">
            {tab === 'incidents' ? (
              <table className="w-full text-[11px] font-mono">
                <thead className="sticky top-0" style={{ background: 'rgba(9,14,31,0.97)' }}>
                  <tr className="border-b border-slate-800/60">
                    {['ID', 'Source IP', 'Attack', 'Threat %', 'Severity', 'Time', 'TX Hash'].map((h) => (
                      <th key={h} className="py-2.5 px-4 text-left text-[9px] text-slate-600 uppercase tracking-widest font-mono font-normal">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.incidents.map((inc) => (
                    <tr
                      key={inc.id}
                      className="border-b border-slate-800/30 hover:bg-cyan-500/[0.03] transition-colors duration-150 group"
                    >
                      <td className="py-2.5 px-4 text-slate-600">{inc.id}</td>
                      <td className="py-2.5 px-4 text-white font-bold">{inc.source_ip}</td>
                      <td className="py-2.5 px-4">
                        <span className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          {inc.attack_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-slate-300 tabular-nums">
                        {(inc.threat_score * 100).toFixed(0)}%
                      </td>
                      <td className="py-2.5 px-4">
                        <span className={
                          inc.severity >= 8 ? 'text-rose-400' :
                          inc.severity >= 5 ? 'text-amber-400' : 'text-cyan-400'
                        }>
                          {inc.severity}/10
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-slate-500 tabular-nums">
                        {new Date(inc.created_at).toLocaleTimeString()}
                      </td>
                      <td className="py-2.5 px-4 text-purple-400">
                        {inc.blockchain_tx?.slice(0, 12) || '—'}{inc.blockchain_tx ? '…' : ''}
                      </td>
                    </tr>
                  ))}
                  {data.incidents.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-slate-700 font-mono text-xs">
                        No incidents logged yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            ) : (
              <table className="w-full text-[11px] font-mono">
                <thead className="sticky top-0" style={{ background: 'rgba(9,14,31,0.97)' }}>
                  <tr className="border-b border-slate-800/60">
                    {['ID', 'TX Hash', 'Block #', 'Attack', 'Severity', 'Gas', 'Status'].map((h) => (
                      <th key={h} className="py-2.5 px-4 text-left text-[9px] text-slate-600 uppercase tracking-widest font-mono font-normal">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.blockchain_records.map((rec, i) => (
                    <tr
                      key={i}
                      className="border-b border-slate-800/30 hover:bg-purple-500/[0.03] transition-colors duration-150"
                    >
                      <td className="py-2.5 px-4 text-slate-600">{rec.id}</td>
                      <td className="py-2.5 px-4 text-purple-400 font-mono">
                        {rec.tx_hash?.slice(0, 14)}…
                      </td>
                      <td className="py-2.5 px-4 text-cyan-400">#{rec.block_number}</td>
                      <td className="py-2.5 px-4">
                        <span className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          {rec.attack_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-amber-400 tabular-nums">{rec.severity}/10</td>
                      <td className="py-2.5 px-4 text-slate-500 tabular-nums">
                        {rec.gas_used?.toLocaleString()}
                      </td>
                      <td className="py-2.5 px-4">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px]">
                          <span className="w-1 h-1 rounded-full bg-emerald-400" />
                          Immutable
                        </span>
                      </td>
                    </tr>
                  ))}
                  {data.blockchain_records.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-slate-700 font-mono text-xs">
                        No blockchain records yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>

          {/* Footer explainer */}
          <div
            className="px-5 py-3 border-t border-slate-800/60 shrink-0"
            style={{ background: 'rgba(2,8,23,0.6)' }}
          >
            <p className="text-[10px] text-slate-600 font-mono leading-relaxed">
              <span className="text-cyan-500/60">ℹ</span>{' '}
              Each <span className="text-purple-400">keccak256</span> hash fingerprints the incident.
              If the SQLite record is modified, the hash will no longer match the on-chain record — proving tampering has occurred.
            </p>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

/* ── Tab button sub-component ── */
function TabBtn({ label, active, color, onClick }) {
  const activeStyles = {
    cyan:   'text-cyan-400 border-b-2 border-cyan-400',
    purple: 'text-purple-400 border-b-2 border-purple-400',
  }
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 text-[10px] font-mono uppercase tracking-widest transition-all duration-200 ${
        active ? activeStyles[color] : 'text-slate-600 hover:text-slate-400'
      }`}
    >
      {label}
    </button>
  )
}
