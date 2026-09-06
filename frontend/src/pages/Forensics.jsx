// [Windows] GraphSentinel — Susheep
// Forensics — full-page version of ForensicsModal content (no modal wrapper)
// Error.md #39: fetch/poll/refresh/error logic and the blockchain records
// table are now shared with ForensicsModal.jsx via useForensicsData and
// BlockchainRecordsTable instead of two independent copies.
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Database, Link2, RefreshCw, ShieldAlert } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import { useForensicsData } from '../hooks/useForensicsData'
import { updateIncidentStatus } from '../services/api'
import CopyableHash from '../components/ui/CopyableHash'
import BlockchainStatusBadge from '../components/ui/BlockchainStatusBadge'
import StatTile from '../components/ui/StatTile'
import BlockchainRecordsTable from '../components/forensics/BlockchainRecordsTable'
import { formatEventTimestamp } from '../utils/formatTimestamp'

export default function Forensics() {
  const [tab, setTab] = useState('incidents')
  const [selectedIncident, setSelectedIncident] = useState(null)
  const { data, loading, fetchError, refresh } = useForensicsData(true, 5000)

  const resolvedIncidentIds = useGraphStore((s) => s.resolvedIncidentIds)
  const resolveIncident = useGraphStore((s) => s.resolveIncident)

  // Error.md H5 — resolution is server-authoritative (`inc.alert_status`), with
  // the local `resolvedIncidentIds` set kept only as an optimistic/offline
  // fallback until the next poll reflects the PATCH.
  const isResolved = (inc) => inc.alert_status === 'resolved' || resolvedIncidentIds.includes(inc.id)
  const activeIncidents = data.incidents.filter((inc) => !isResolved(inc))

  const markResolved = (incidentId) => {
    resolveIncident(incidentId) // optimistic + offline fallback
    updateIncidentStatus(incidentId, 'resolved').catch(() => { /* keep local */ })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#1b1f27', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Forensics
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: '#7c3aed', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
              Chain ID: {data.chain_id ?? '—'}
            </span>
            {data.contract_address && (
              <span style={{ fontSize: 11, color: '#7c3aed', fontFamily: "'DM Mono', monospace", background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)', padding: '2px 8px', borderRadius: 4 }}>
                {data.contract_address.slice(0, 14)}…
              </span>
            )}
            {loading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <RefreshCw size={11} style={{ color: '#3b56d9' }} className="spin-slow" />
                <span style={{ color: '#3b56d9', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>SYNCING</span>
              </div>
            )}
          </div>
        </div>
        <button
          id="forensics-refresh"
          onClick={refresh}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 6,
            border: '1px solid rgba(17,20,26,0.12)', background: 'rgba(17,20,26,0.05)',
            color: '#5a616e', fontSize: 11, fontFamily: "'DM Mono', monospace",
            cursor: 'pointer', transition: 'all 150ms',
          }}
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Visible fetch-failure banner — the request itself failed (network
          error, 5xx, timeout), distinct from data.blockchain_error which
          means the request succeeded but Ganache is offline. Previously
          silently swallowed, so a backend outage looked identical to "no
          incidents yet." */}
      {fetchError && (
        <div
          role="alert"
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 14px', borderRadius: 8,
            border: '1px solid rgba(224,60,60,0.3)', background: 'rgba(224,60,60,0.08)',
            color: '#E03C3C', fontSize: 12, fontFamily: "'DM Mono', monospace",
          }}
        >
          <ShieldAlert size={14} style={{ flexShrink: 0 }} />
          Failed to refresh forensics data: {fetchError}
        </div>
      )}

      {/* Stat summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <StatTile label="Total Incidents" value={data.total_incidents} color="#3b56d9" />
        <StatTile label="On-Chain Records" value={data.total_on_chain} color="#7c3aed" />
        <StatTile label="Active Incidents" value={activeIncidents.length} color="#E03C3C" />
        <StatTile label="Blockchain Records" value={data.blockchain_records.length} color="#12a672" />
      </div>

      {/* Main content: case list + detail */}
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}>
        {/* Left: Case list */}
        <div className="gs-panel" style={{ padding: 0, overflow: 'hidden', height: 'fit-content', maxHeight: 600 }}>
          <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(17,20,26,0.08)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldAlert size={13} style={{ color: '#E03C3C' }} />
            <span style={{ color: '#E03C3C', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Incidents ({activeIncidents.length})
            </span>
          </div>
          <div style={{ overflowY: 'auto', maxHeight: 540 }}>
            {activeIncidents.map((inc, i) => (
              <div
                key={inc.id}
                onClick={() => setSelectedIncident(inc)}
                style={{
                  padding: '10px 14px',
                  borderBottom: '1px solid rgba(17,20,26,0.05)',
                  cursor: 'pointer',
                  background: selectedIncident?.id === inc.id ? 'rgba(79,110,247,0.08)' : 'transparent',
                  borderLeft: selectedIncident?.id === inc.id ? '2px solid #3b56d9' : '2px solid transparent',
                  transition: 'all 150ms',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{
                    fontSize: 9, fontWeight: 700, fontFamily: "'DM Mono', monospace", letterSpacing: '0.08em',
                    color: inc.severity >= 8 ? '#E03C3C' : inc.severity >= 5 ? '#b7791f' : '#3b56d9',
                    textTransform: 'uppercase',
                  }}>
                    {inc.severity >= 8 ? 'CRITICAL' : inc.severity >= 5 ? 'WARNING' : 'INFO'}
                  </span>
                  <span style={{ color: '#5a616e', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                    {inc.attack_type}
                  </span>
                  {inc.is_blocked && (
                    <span style={{ marginLeft: 'auto', fontSize: 9, color: '#E03C3C', fontFamily: "'DM Mono', monospace", background: 'rgba(224,60,60,0.1)', padding: '1px 5px', borderRadius: 3, border: '1px solid rgba(224,60,60,0.2)' }}>
                      ISOLATED
                    </span>
                  )}
                </div>
                <div style={{ color: '#1b1f27', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, marginBottom: 2 }}>
                  {inc.source_ip}
                </div>
                <div style={{ color: '#9aa1ad', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                  {formatEventTimestamp(inc.created_at)}
                </div>
              </div>
            ))}
            {activeIncidents.length === 0 && (
              <div style={{ padding: '32px 16px', textAlign: 'center', color: '#9aa1ad', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                <div style={{ marginBottom: 4 }}>No incidents logged</div>
                <div style={{ fontSize: 10, color: '#e2e5ea' }}>
                  {fetchError
                    ? 'Check the error above — this may be stale, not empty'
                    : 'Incidents appear here once real traffic crosses the threat threshold, or use Simulate in the top bar to trigger one'}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Case detail */}
        <div>
          {selectedIncident ? (
            <AnimatePresence mode="wait">
              <motion.div
                key={selectedIncident.id}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -12 }}
                style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
              >
                {/* Incident summary card */}
                <div className="gs-panel" style={{ padding: '16px 18px', borderLeft: '3px solid #3b56d9' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ color: '#1b1f27', fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
                        Incident #{selectedIncident.id}
                      </span>
                      <IsolationBadge isBlocked={selectedIncident.is_blocked} />
                    </div>
                    <div style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                      {formatEventTimestamp(selectedIncident.created_at)}
                    </div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                    <DetailRow label="Attack Type" value={selectedIncident.attack_type || 'Unknown'} />
                    <DetailRow label="Source IP" value={selectedIncident.source_ip || '—'} />
                    <DetailRow label="Threat Score" value={selectedIncident.threat_score !== null && selectedIncident.threat_score !== undefined ? `${(selectedIncident.threat_score * 100).toFixed(0)}%` : '—'} />
                    <DetailRow label="Severity" value={selectedIncident.severity !== null && selectedIncident.severity !== undefined ? `${selectedIncident.severity}/10` : '—'} color={selectedIncident.severity >= 8 ? '#E03C3C' : selectedIncident.severity >= 5 ? '#b7791f' : '#3b56d9'} />
                    <div>
                      <div style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 3 }}>Enforcement</div>
                      <EnforcementPill status={selectedIncident.enforcement_status} />
                    </div>
                    <div>
                      <div style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 3 }}>Data Source</div>
                      <ProvenancePill source={selectedIncident.data_source} />
                    </div>
                  </div>
                </div>

                {/* Attack timeline */}
                <div className="gs-panel" style={{ padding: '14px 18px' }}>
                  <div style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
                    Attack Timeline
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                    {(() => {
                      const steps = deriveAttackTimelineSteps(selectedIncident)
                      return steps.map((item, i) => (
                        <div key={i} style={{ display: 'flex', gap: 12, position: 'relative', paddingBottom: 14 }}>
                          {/* Line */}
                          {i < steps.length - 1 && (
                            <div style={{ position: 'absolute', left: 7, top: 16, width: 1, height: 'calc(100% - 4px)', background: 'rgba(17,20,26,0.08)' }} />
                          )}
                          <div style={{ width: 15, height: 15, borderRadius: '50%', background: `${item.color}20`, border: `1.5px solid ${item.color}`, flexShrink: 0, marginTop: 2 }} />
                          <div>
                            <div style={{ color: '#1b1f27', fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 600, marginBottom: 2 }}>{item.step}</div>
                            <div style={{ color: '#727a86', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{item.detail}</div>
                          </div>
                        </div>
                      ))
                    })()}
                  </div>
                </div>

                {/* Evidence */}
                <div className="gs-panel" style={{ padding: '14px 18px', borderLeft: '3px solid #7c3aed' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Link2 size={13} style={{ color: '#7c3aed' }} />
                      <span style={{ color: '#7c3aed', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600 }}>
                        Blockchain Evidence
                      </span>
                    </div>
                    <BlockchainStatusBadge status={selectedIncident.blockchain_status || selectedIncident.tx_status} />
                  </div>

                  {selectedIncident.blockchain_tx ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 6, background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.15)' }}>
                        <span style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase' }}>Transaction</span>
                        <span style={{ color: '#7c3aed', fontSize: 11, fontFamily: "'DM Mono', monospace", marginLeft: 'auto' }}>
                          <CopyableHash value={selectedIncident.blockchain_tx} prefixLen={selectedIncident.blockchain_tx.length} />
                        </span>
                      </div>

                      {/* Blockchain Metadata Grid */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, padding: '8px 10px', background: 'rgba(17,20,26,0.04)', borderRadius: 6, border: '1px solid rgba(17,20,26,0.05)' }}>
                        <div>
                          <div style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>Chain ID</div>
                          <div style={{ color: '#1b1f27', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
                            {selectedIncident.blockchain_chain_id ?? data.chain_id ?? '—'}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>Contract</div>
                          <div style={{ color: '#1b1f27', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600 }} title={selectedIncident.blockchain_contract_address || data.contract_address || undefined}>
                            {selectedIncident.blockchain_contract_address ? `${selectedIncident.blockchain_contract_address.slice(0, 8)}…` : (data.contract_address ? `${data.contract_address.slice(0, 8)}…` : '—')}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>Block #</div>
                          <div style={{ color: '#7c3aed', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
                            {selectedIncident.blockchain_block_number !== null && selectedIncident.blockchain_block_number !== undefined ? `#${selectedIncident.blockchain_block_number}` : 'Block —'}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>On-Chain Log ID</div>
                          <div style={{ color: '#7c3aed', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
                            {selectedIncident.blockchain_incident_id !== null && selectedIncident.blockchain_incident_id !== undefined ? `#${selectedIncident.blockchain_incident_id}` : 'Log ID —'}
                          </div>
                        </div>
                      </div>

                      {/* Retry attempts if relevant */}
                      {(selectedIncident.blockchain_retry_count > 0 || selectedIncident.blockchain_status === 'retry') && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 4, background: 'rgba(232,146,42,0.08)', border: '1px solid rgba(232,146,42,0.2)', color: '#b7791f', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                          <span>Retry attempts: {selectedIncident.blockchain_retry_count || 1}</span>
                        </div>
                      )}

                      {/* Failure/error details if present */}
                      {selectedIncident.blockchain_last_error && (
                        <div style={{ padding: '8px 10px', borderRadius: 4, background: 'rgba(224,60,60,0.08)', border: '1px solid rgba(224,60,60,0.2)', color: '#E03C3C', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                          <span style={{ fontWeight: 600 }}>Last error:</span> {selectedIncident.blockchain_last_error}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ color: '#9aa1ad', fontSize: 11, fontFamily: "'DM Mono', monospace", padding: '4px 0' }}>
                      No transaction recorded
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: 10 }}>
                  <ActionBtn label="Export PDF Report" color="#3b56d9" onClick={() => window.print()} />
                  <ActionBtn
                    label="Mark Resolved"
                    color="#12a672"
                    onClick={() => {
                      markResolved(selectedIncident.id)
                      setSelectedIncident(null)
                    }}
                  />
                </div>
              </motion.div>
            </AnimatePresence>
          ) : (
            <div className="gs-panel" style={{ padding: '60px 0', textAlign: 'center' }}>
              <Database size={32} style={{ color: '#9aa1ad', margin: '0 auto 12px', display: 'block' }} />
              <div style={{ color: '#9aa1ad', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
                Select an incident from the left panel to view details
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Blockchain records table */}
      <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(17,20,26,0.08)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link2 size={13} style={{ color: '#7c3aed' }} />
          <span style={{ color: '#7c3aed', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Blockchain Records
          </span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <BlockchainRecordsTable records={data.blockchain_records} blockchainError={data.blockchain_error} />
        </div>
      </div>
    </div>
  )
}

function DetailRow({ label, value, color = '#5a616e' }) {
  return (
    <div>
      <div style={{ color: '#9aa1ad', fontSize: 9, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 2 }}>{label}</div>
      <div style={{ color, fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{value}</div>
    </div>
  )
}

function IsolationBadge({ isBlocked }) {
  if (isBlocked === true) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px', borderRadius: 4, background: 'rgba(224,60,60,0.1)', color: '#E03C3C', border: '1px solid rgba(224,60,60,0.25)', fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#E03C3C' }} />
        ISOLATED
      </span>
    )
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px', borderRadius: 4, background: 'rgba(46,204,138,0.1)', color: '#12a672', border: '1px solid rgba(46,204,138,0.25)', fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#12a672' }} />
      ACTIVE
    </span>
  )
}

function EnforcementPill({ status }) {
  const norm = typeof status === 'string' ? status.trim().toLowerCase() : ''
  if (norm === 'enforced') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(46,204,138,0.1)', color: '#12a672', border: '1px solid rgba(46,204,138,0.25)', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', fontWeight: 600 }}>
        ENFORCED
      </span>
    )
  }
  if (norm === 'simulated') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(79,110,247,0.1)', color: '#3b56d9', border: '1px solid rgba(79,110,247,0.25)', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', fontWeight: 600 }}>
        SIMULATED
      </span>
    )
  }
  if (norm === 'pending_enforcement' || norm === 'pending_unblock') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(232,146,42,0.1)', color: '#b7791f', border: '1px solid rgba(232,146,42,0.25)', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', fontWeight: 600 }}>
        PENDING
      </span>
    )
  }
  if (norm === 'failed') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(224,60,60,0.1)', color: '#E03C3C', border: '1px solid rgba(224,60,60,0.25)', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', fontWeight: 600 }}>
        FAILED
      </span>
    )
  }
  if (norm === 'removed') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(46,204,138,0.1)', color: '#12a672', border: '1px solid rgba(46,204,138,0.25)', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', fontWeight: 600 }}>
        REMOVED
      </span>
    )
  }
  if (norm === 'not_requested') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(17,20,26,0.06)', color: '#727a86', border: '1px solid rgba(17,20,26,0.12)', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', fontWeight: 500 }}>
        NOT REQUESTED
      </span>
    )
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(17,20,26,0.06)', color: '#5a616e', border: '1px solid rgba(17,20,26,0.12)', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', fontWeight: 500 }}>
      {status || 'Unknown'}
    </span>
  )
}

function ProvenancePill({ source }) {
  const norm = typeof source === 'string' ? source.trim().toLowerCase() : ''
  if (norm === 'ovs') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(46,204,138,0.1)', color: '#12a672', border: '1px solid rgba(46,204,138,0.2)', fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
        OVS LIVE
      </span>
    )
  }
  if (norm === 'demo') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(232,146,42,0.1)', color: '#b7791f', border: '1px solid rgba(232,146,42,0.2)', fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
        DEMO FLOW
      </span>
    )
  }
  if (norm === 'simulation') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(79,110,247,0.1)', color: '#3b56d9', border: '1px solid rgba(79,110,247,0.2)', fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
        SIMULATION
      </span>
    )
  }
  if (norm === 'manual') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(17,20,26,0.06)', color: '#5a616e', border: '1px solid rgba(17,20,26,0.12)', fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 500 }}>
        MANUAL
      </span>
    )
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, background: 'rgba(17,20,26,0.06)', color: '#727a86', border: '1px solid rgba(17,20,26,0.12)', fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 500 }}>
      {source || 'Unknown source'}
    </span>
  )
}

function ActionBtn({ label, color, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 16px', borderRadius: 6, cursor: 'pointer',
        border: `1px solid ${color}30`, background: `${color}10`, color,
        fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 500, transition: 'all 150ms',
      }}
    >
      {label}
    </button>
  )
}

function deriveAttackTimelineSteps(incident) {
  if (!incident) return []

  const ip = incident.source_ip || 'Source host'
  const normType = typeof incident.attack_type === 'string' ? incident.attack_type.trim().toLowerCase() : ''
  const displayType = incident.attack_type || 'Unknown'
  const threatPercent = incident.threat_score !== null && incident.threat_score !== undefined
    ? `${(incident.threat_score * 100).toFixed(0)}%`
    : '—'

  // Step 1: Detection / Activity Observation (strictly from available fields)
  let detectionStep
  if (normType === 'ddos') {
    detectionStep = {
      step: 'DDoS activity detected',
      detail: `Detected activity from ${ip}`,
      color: '#b7791f',
    }
  } else if (normType === 'portscan') {
    detectionStep = {
      step: 'PortScan activity detected',
      detail: `Detected activity from ${ip}`,
      color: '#b7791f',
    }
  } else if (normType === 'sshbrute') {
    detectionStep = {
      step: 'SSHBrute activity detected',
      detail: `Detected activity from ${ip}`,
      color: '#b7791f',
    }
  } else if (normType === 'doshulk') {
    detectionStep = {
      step: 'DoSHulk activity detected',
      detail: `Detected activity from ${ip}`,
      color: '#b7791f',
    }
  } else if (normType === 'botnet') {
    detectionStep = {
      step: 'Botnet activity detected',
      detail: `Detected activity from ${ip}`,
      color: '#b7791f',
    }
  } else {
    detectionStep = {
      step: 'Anomalous activity detected',
      detail: `Detected activity from ${ip}`,
      color: '#b7791f',
    }
  }

  // Step 2: Classification (GraphSAGE threat assessment)
  const classificationStep = {
    step: 'GraphSAGE classified',
    detail: `${displayType} classified (threat score: ${threatPercent})`,
    color: '#E03C3C',
  }

  // Step 3: Enforcement State (truthful OVS / daemon execution state)
  const normEnforcement = typeof incident.enforcement_status === 'string' ? incident.enforcement_status.trim().toLowerCase() : ''
  let enforcementStep
  if (normEnforcement === 'enforced') {
    enforcementStep = {
      step: 'OpenFlow rule installed',
      detail: incident.is_blocked ? 'Host isolated via OVS drop flow' : 'Active drop rule confirmed',
      color: '#12a672',
    }
  } else if (normEnforcement === 'simulated') {
    enforcementStep = {
      step: 'Simulation executed',
      detail: 'Simulated isolation rule triggered',
      color: '#3b56d9',
    }
  } else if (normEnforcement === 'pending_enforcement' || normEnforcement === 'pending_unblock') {
    enforcementStep = {
      step: 'Enforcement pending',
      detail: 'Daemon isolation action queued',
      color: '#b7791f',
    }
  } else if (normEnforcement === 'failed') {
    enforcementStep = {
      step: 'Enforcement failed',
      detail: 'OVS daemon rule installation failed',
      color: '#E03C3C',
    }
  } else if (normEnforcement === 'removed') {
    enforcementStep = {
      step: 'Isolation removed',
      detail: 'OpenFlow drop rule cleared',
      color: '#12a672',
    }
  } else if (normEnforcement === 'not_requested') {
    enforcementStep = {
      step: 'No enforcement requested',
      detail: incident.is_blocked ? 'Host marked blocked' : 'Monitoring without active isolation',
      color: '#727a86',
    }
  } else {
    enforcementStep = {
      step: 'Enforcement: ' + (incident.enforcement_status || 'Unknown'),
      detail: incident.is_blocked ? 'Host marked isolated' : 'No active drop rule',
      color: '#727a86',
    }
  }

  // Step 4: Blockchain Evidence (truthful ledger recording state)
  const isConfirmed = incident.blockchain_status === 'confirmed' || incident.tx_status === 'confirmed'
  const isPending = incident.blockchain_status === 'pending' || incident.blockchain_status === 'submitting' || incident.tx_status === 'pending'
  const isRetry = incident.blockchain_status === 'retry'
  const isFailed = incident.blockchain_status === 'failed' || incident.tx_status === 'missing' || incident.tx_status === 'wrong_contract'

  let blockchainStep
  if (isConfirmed) {
    blockchainStep = {
      step: 'Logged on-chain',
      detail: incident.blockchain_block_number ? `Verified in block #${incident.blockchain_block_number}` : 'Blockchain record verified',
      color: '#12a672',
    }
  } else if (isPending) {
    blockchainStep = {
      step: 'Pending confirmation',
      detail: 'Transaction broadcast to ledger',
      color: '#b7791f',
    }
  } else if (isRetry) {
    blockchainStep = {
      step: 'Blockchain retry scheduled',
      detail: incident.blockchain_last_error || 'Outbox retry pending',
      color: '#b7791f',
    }
  } else if (isFailed) {
    blockchainStep = {
      step: 'Blockchain write failed',
      detail: incident.blockchain_last_error || 'Verification failed',
      color: '#E03C3C',
    }
  } else if (incident.blockchain_tx) {
    blockchainStep = {
      step: 'Transaction recorded',
      detail: 'Blockchain transaction created',
      color: '#7c3aed',
    }
  } else {
    blockchainStep = {
      step: 'No blockchain record',
      detail: 'Incident not recorded to ledger',
      color: '#727a86',
    }
  }

  return [detectionStep, classificationStep, enforcementStep, blockchainStep]
}
