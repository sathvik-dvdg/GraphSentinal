// [Windows] GraphSentinel — Susheep
// Axios API client — calls Sairaj's FastAPI backend
// Vite proxy in vite.config.js redirects /api → http://localhost:8000
import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  // The FastAPI backend itself is consistently fast (single-digit ms,
  // confirmed by timing it directly) — but in the Docker dev environment,
  // Vite's dev-server proxy sits in front of it with `watch.usePolling: true`
  // (needed for file-change propagation through the Windows/WSL2 bind mount),
  // which periodically busies the same single-threaded process handling the
  // proxy. That occasionally pushed a proxied request past 5s, which axios
  // then aborted client-side (surfacing as a false "Error: undefined" — no
  // response was ever slow from the backend, the request just never reached
  // it in time). 15s gives real headroom without masking an actually-dead
  // backend for anything but a truly hung connection.
  timeout: 15000,
})

// Error.md #18/#27 — every /api/v1/* route now requires either a real
// operator session or the service API key. Browser clients use the session
// exclusively; the API token is no longer shipped to the browser at all
// (previously VITE_BACKEND_API_TOKEN was embedded in the frontend bundle —
// "Keep service API keys server-side only" was the explicit required fix).
let sessionToken = null
export const setSessionToken = (token) => { sessionToken = token }
export const clearSessionToken = () => { sessionToken = null }

// Registered by useAuthStore so a 401 from any call (session expired,
// revoked, or backend restarted and forgot in-memory sessions) immediately
// reflects in the UI instead of the app silently failing every poll.
let unauthorizedHandler = null
export const setUnauthorizedHandler = (fn) => { unauthorizedHandler = fn }

api.interceptors.request.use((config) => {
  console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`)
  if (sessionToken && !config.headers?.Authorization) {
    config.headers = { ...config.headers, Authorization: `Bearer ${sessionToken}` }
  }
  return config
})

api.interceptors.response.use(
  (r) => r.data,
  (err) => {
    // A cancelled request (React 18 StrictMode double-invokes effects in
    // dev, aborting the first mount's in-flight calls) is not a backend
    // failure — logging it as "[API] Error: undefined ..." reads as a real
    // outage when the retried request actually succeeds a moment later.
    if (axios.isCancel(err) || err.code === 'ERR_CANCELED') {
      throw err
    }
    console.error(`[API] Error: ${err.response?.status} ${err.config?.url}`)
    if (err.response?.status === 401 && !err.config?.url?.includes('/auth/login')) {
      unauthorizedHandler?.()
    }
    throw err
  }
)

export const login = (username, password) => api.post('/api/v1/auth/login', { username, password })
export const logout = () => api.post('/api/v1/auth/logout').catch(() => {})
export const getMe = () => api.get('/api/v1/auth/me')

export const getGraph = () => api.get('/api/v1/graph')
export const getStats = () => api.get('/api/v1/stats')
export const getAlerts = (limit = 50) =>
  api.get('/api/v1/alerts', { params: { limit } })
export const getBlocked = () => api.get('/api/v1/blocked')
export const getForensics = () => api.get('/api/v1/forensics')
export const getTimeline = (last = '60min') =>
  api.get('/api/v1/timeline', { params: { last } })
export const getHealth = () => api.get('/health')

export const blockIP = (ip, action = 'block', reason = 'MANUAL_OVERRIDE') =>
  api.post('/api/v1/block', { ip, action, reason })
export const getEnforcementActions = (limit = 100) =>
  api.get('/api/v1/enforcement-actions', { params: { limit } })

export const analyzeFlows = (flows) => api.post('/api/v1/analyze', { flows })

export const getSettings = () => api.get('/api/v1/settings')
export const updateThreatThreshold = (threat_threshold) =>
  api.patch('/api/v1/settings', { threat_threshold })

export default api
