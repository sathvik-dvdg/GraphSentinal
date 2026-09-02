// [Windows] GraphSentinel — Susheep
// useForensicsData — Error.md #39: Forensics.jsx and ForensicsModal.jsx each
// had their own copy of this fetch/poll/refresh/error logic. Consolidating
// also fixes a real gap: ForensicsModal still had `.catch(() => {})`
// silently swallowing fetch failures (the same bug fixed in Forensics.jsx
// under #26) — pulling both onto one hook means a fix here covers both.
import { useState, useEffect, useRef, useCallback } from 'react'
import { getForensics } from '../services/api'

const EMPTY_DATA = {
  incidents: [],
  blockchain_records: [],
  total_incidents: 0,
  total_on_chain: 0,
  contract_address: null,
  chain_id: null,
  blockchain_error: null,
}

export function useForensicsData(active = true, pollMs = 5000) {
  const [data, setData] = useState(EMPTY_DATA)
  const [loading, setLoading] = useState(false)
  const [fetchError, setFetchError] = useState(null)
  const intervalRef = useRef(null)

  const refresh = useCallback(() => {
    setLoading(true)
    return getForensics()
      .then((res) => {
        setData(res)
        setFetchError(null)
      })
      .catch((err) => setFetchError(err.message || 'Failed to reach the backend'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!active) return
    let isMounted = true
    const tick = () => { if (isMounted) refresh() }
    tick()
    intervalRef.current = setInterval(tick, pollMs)
    return () => {
      isMounted = false
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [active, pollMs, refresh])

  return { data, loading, fetchError, refresh }
}
