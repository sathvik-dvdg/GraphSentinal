// [Windows] GraphSentinel — Susheep
// AuditLog — Error.md H6: surfaces GET /api/v1/audit-logs (operator-level
// who-did-what: manual blocks/unblocks, settings changes). The endpoint is
// admin-only, so a 403 is shown as an explicit "needs admin" state rather
// than an empty table.
import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { ScrollText, RefreshCw, ShieldAlert } from 'lucide-react'
import { getAuditLogs } from '../services/api'
import { formatEventTimestamp } from '../utils/formatTimestamp'

const PAGE = 100

export default function AuditLog() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState('loading') // loading | ok | forbidden | error
  const [loadingMore, setLoadingMore] = useState(false)

  const load = useCallback((nextOffset = 0, append = false) => {
    if (append) setLoadingMore(true)
    else setStatus('loading')
    getAuditLogs(PAGE, nextOffset)
      .then((res) => {
        setRows((prev) => (append ? [...prev, ...res.audit_logs] : res.audit_logs))
        setTotal(res.total ?? res.audit_logs.length)
        setOffset(nextOffset)
        setStatus('ok')
      })
      .catch((err) => {
        setStatus(err?.response?.status === 403 ? 'forbidden' : 'error')
      })
      .finally(() => setLoadingMore(false))
  }, [])

  useEffect(() => { load(0, false) }, [load])

  const hasMore = rows.length < total

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#1b1f27', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
            Audit Log
          </h1>
          <p style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
            Control-plane actions · operator identity · request correlation
          </p>
        </div>
        <button
          onClick={() => load(0, false)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 6,
            border: '1px solid rgba(17,20,26,0.12)', background: 'rgba(17,20,26,0.05)',
            color: '#5a616e', fontSize: 11, fontFamily: "'DM Mono', monospace", cursor: 'pointer',
          }}
        >
          <RefreshCw size={12} className={status === 'loading' ? 'spin-slow' : undefined} /> Refresh
        </button>
      </div>

      {status === 'forbidden' && (
        <div className="gs-panel" style={{ padding: '32px', textAlign: 'center', color: '#b7791f', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
          <ShieldAlert size={28} style={{ margin: '0 auto 10px' }} />
          Administrative privilege is required to view the audit log.
        </div>
      )}

      {status === 'error' && (
        <div role="alert" className="gs-panel" style={{ padding: '16px', color: '#E03C3C', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
          Failed to load the audit log — the backend may be unreachable.
        </div>
      )}

      {status === 'ok' && (
        <>
          <div className="gs-panel" style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <ScrollText size={13} style={{ color: '#5a616e' }} />
            <span style={{ color: '#5a616e', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
              {rows.length} of {total} entries
            </span>
          </div>

          <div className="gs-panel" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table className="gs-table" style={{ width: '100%' }}>
                <thead style={{ background: '#eef1f5' }}>
                  <tr>
                    {['Time', 'Actor', 'Role', 'Action', 'Target', 'Status', 'Request ID'].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <motion.tr key={r.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: Math.min(i, 20) * 0.02 }}>
                      <td style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>
                        {formatEventTimestamp(r.timestamp)}
                      </td>
                      <td style={{ color: '#1b1f27', fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{r.actor_identity}</td>
                      <td style={{ color: '#5a616e', fontFamily: "'DM Mono', monospace", fontSize: 10, textTransform: 'uppercase' }}>{r.actor_role}</td>
                      <td>
                        <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: 'rgba(79,110,247,0.1)', color: '#3b56d9', border: '1px solid rgba(79,110,247,0.2)', fontFamily: "'DM Mono', monospace" }}>
                          {r.action}
                        </span>
                      </td>
                      <td style={{ color: '#5a616e', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>{r.target_resource}</td>
                      <td style={{ color: r.status === 'success' ? '#12a672' : '#E03C3C', fontFamily: "'DM Mono', monospace", fontSize: 10, textTransform: 'uppercase' }}>{r.status}</td>
                      <td style={{ color: '#9aa1ad', fontFamily: "'DM Mono', monospace", fontSize: 10 }}>{r.request_id || '—'}</td>
                    </motion.tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '32px 0', color: '#9aa1ad', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
                        No audit entries recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {hasMore && (
            <button
              onClick={() => load(offset + PAGE, true)}
              disabled={loadingMore}
              style={{
                alignSelf: 'center', padding: '8px 20px', borderRadius: 6,
                border: '1px solid rgba(79,110,247,0.3)', background: 'rgba(79,110,247,0.08)',
                color: '#3b56d9', fontSize: 12, fontFamily: "'DM Mono', monospace", cursor: 'pointer',
              }}
            >
              {loadingMore ? 'Loading…' : `Load ${Math.min(PAGE, total - rows.length)} more`}
            </button>
          )}
        </>
      )}
    </div>
  )
}
