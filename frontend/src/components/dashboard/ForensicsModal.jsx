// [Windows] GraphSentinel — Susheep
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { getForensics } from '../../services/api'

export default function ForensicsModal({ isOpen, onClose }) {
  const [tab, setTab] = useState('incidents')
  const [data, setData] = useState({ incidents: [], blockchain_records: [], total_incidents: 0, total_on_chain: 0, contract_address: null })

  useEffect(() => {
    if (isOpen) {
      getForensics()
        .then((res) => setData(res))
        .catch(() => {})
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center"
        style={{ background: 'rgba(0,0,0,0.8)' }}
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-gs-card rounded-xl border border-gs-border w-[90vw] max-w-4xl max-h-[80vh] overflow-hidden flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gs-border shrink-0">
            <div className="flex items-center gap-4">
              <h2 className="text-base font-bold text-white font-mono">🔍 FORENSICS REPORT</h2>
              {data.contract_address && (
                <span className="text-xs text-gray-500 font-mono">
                  Contract: {data.contract_address?.slice(0, 10)}...
                </span>
              )}
              <span className="text-xs text-gray-600 font-mono">Chain ID: 1337</span>
            </div>
            <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
              <X size={18} />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-0 border-b border-gs-border shrink-0">
            <button
              onClick={() => setTab('incidents')}
              className={`px-4 py-2 text-xs font-mono transition-colors ${
                tab === 'incidents'
                  ? 'text-gs-accent border-b-2 border-gs-accent'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              INCIDENTS ({data.total_incidents})
            </button>
            <button
              onClick={() => setTab('blockchain')}
              className={`px-4 py-2 text-xs font-mono transition-colors ${
                tab === 'blockchain'
                  ? 'text-gs-chain border-b-2 border-gs-chain'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              BLOCKCHAIN RECORDS ({data.total_on_chain})
            </button>
          </div>

          {/* Table content */}
          <div className="flex-1 overflow-auto p-4">
            {tab === 'incidents' ? (
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-gray-500 border-b border-gs-border">
                    <th className="py-2 text-left">ID</th>
                    <th className="py-2 text-left">Source IP</th>
                    <th className="py-2 text-left">Attack</th>
                    <th className="py-2 text-left">Threat %</th>
                    <th className="py-2 text-left">Severity</th>
                    <th className="py-2 text-left">Time</th>
                    <th className="py-2 text-left">TX Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {data.incidents.map((inc) => (
                    <tr key={inc.id} className="border-b border-gs-border/50 hover:bg-gs-bg/50">
                      <td className="py-2 text-gray-400">{inc.id}</td>
                      <td className="py-2 text-white">{inc.source_ip}</td>
                      <td className="py-2 text-red-400">{inc.attack_type}</td>
                      <td className="py-2 text-white">{(inc.threat_score * 100).toFixed(0)}%</td>
                      <td className="py-2">
                        <span className={inc.severity >= 8 ? 'text-red-400' : inc.severity >= 5 ? 'text-yellow-400' : 'text-blue-400'}>
                          {inc.severity}/10
                        </span>
                      </td>
                      <td className="py-2 text-gray-400">{new Date(inc.created_at).toLocaleTimeString()}</td>
                      <td className="py-2 text-purple-400">{inc.blockchain_tx?.slice(0, 12) || '—'}...</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-gray-500 border-b border-gs-border">
                    <th className="py-2 text-left">ID</th>
                    <th className="py-2 text-left">TX Hash</th>
                    <th className="py-2 text-left">Block #</th>
                    <th className="py-2 text-left">Attack</th>
                    <th className="py-2 text-left">Severity</th>
                    <th className="py-2 text-left">Gas</th>
                    <th className="py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.blockchain_records.map((rec, i) => (
                    <tr key={i} className="border-b border-gs-border/50 hover:bg-gs-bg/50">
                      <td className="py-2 text-gray-400">{rec.id}</td>
                      <td className="py-2 text-purple-400">{rec.tx_hash?.slice(0, 16)}...</td>
                      <td className="py-2 text-white">#{rec.block_number}</td>
                      <td className="py-2 text-red-400">{rec.attack_type}</td>
                      <td className="py-2 text-yellow-400">{rec.severity}/10</td>
                      <td className="py-2 text-gray-400">{rec.gas_used}</td>
                      <td className="py-2">
                        <span className="bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded text-xs">
                          ✓ Immutable
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Tamper-proof explainer */}
          <div className="p-4 border-t border-gs-border bg-gs-bg/50 shrink-0">
            <p className="text-xs text-gray-500 font-mono leading-relaxed">
              ℹ️ Each keccak256 hash fingerprints the incident. If the SQLite record is modified,
              the hash will no longer match the on-chain record — proving tampering has occurred.
            </p>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
