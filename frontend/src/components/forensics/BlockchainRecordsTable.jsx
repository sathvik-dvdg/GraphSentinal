// [Windows] GraphSentinel — Susheep
// BlockchainRecordsTable — Error.md #39: identical table (same 7 columns,
// same field mapping) previously duplicated in Forensics.jsx and
// ForensicsModal.jsx.
import { Link2 } from 'lucide-react'
import CopyableHash from '../ui/CopyableHash'
import BlockchainStatusBadge from '../ui/BlockchainStatusBadge'

const HEADERS = ['ID', 'TX Hash', 'Block #', 'Attack', 'Severity', 'Gas', 'Status']

export default function BlockchainRecordsTable({ records, blockchainError, stickyHeader = false }) {
  return (
    <table className="gs-table w-full">
      <thead className={stickyHeader ? 'sticky top-0' : undefined} style={{ background: '#eef1f5' }}>
        <tr>
          {HEADERS.map((h) => <th key={h}>{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {records.map((rec, i) => (
          <tr key={rec.id ?? i}>
            <td className="text-gs-faint">{rec.id}</td>
            <td className="text-gs-chain tabular-nums"><CopyableHash value={rec.tx_hash} iconSize={9} /></td>
            <td className="text-gs-accent tabular-nums">#{rec.block_number}</td>
            <td>
              <span className="px-1.5 py-0.5 rounded-md bg-gs-threat-soft text-gs-threat border border-gs-threat/20 text-[10px]">
                {rec.attack_type}
              </span>
            </td>
            <td className="text-gs-warn tabular-nums">{rec.severity}/10</td>
            <td className="text-gs-muted tabular-nums">{rec.gas_used?.toLocaleString()}</td>
            <td>
              <BlockchainStatusBadge status={rec.status} />
            </td>
          </tr>
        ))}
        {records.length === 0 && (
          <tr>
            <td colSpan={7} className="py-10 text-center">
              <div className="flex flex-col items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gs-chain-soft border border-gs-chain/20 flex items-center justify-center">
                  <Link2 size={16} className="text-gs-chain/40" aria-hidden="true" />
                </div>
                <p className="text-gs-faint font-mono text-xs">
                  {blockchainError ? `No blockchain records — ${blockchainError}` : 'No blockchain records.'}
                </p>
                {!blockchainError && (
                  <p className="text-gs-faint font-mono text-[10px] opacity-70">
                    Ganache may be offline. Records appear when incidents are verified on-chain.
                  </p>
                )}
              </div>
            </td>
          </tr>
        )}
      </tbody>
    </table>
  )
}
