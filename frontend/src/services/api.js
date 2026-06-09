// [Windows] GraphSentinel — Susheep
// Axios API client — calls Sairaj's FastAPI backend
// Vite proxy in vite.config.js redirects /api → http://localhost:8000
import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  timeout: 5000,
})

api.interceptors.request.use((config) => {
  console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`)
  return config
})

api.interceptors.response.use(
  (r) => r.data,
  (err) => {
    console.error(`[API] Error: ${err.response?.status} ${err.config?.url}`)
    throw err
  }
)

export const getGraph = () => api.get('/api/v1/graph')
export const getStats = () => api.get('/api/v1/stats')
export const getAlerts = (limit = 50) =>
  api.get('/api/v1/alerts', { params: { limit } })
export const getBlocked = () => api.get('/api/v1/blocked')
export const getForensics = () => api.get('/api/v1/forensics')
export const getTimeline = (last = '60min') =>
  api.get('/api/v1/timeline', { params: { last } })
export const blockIP = (ip, action = 'block', reason = 'MANUAL_OVERRIDE') => {
  const token = import.meta.env.VITE_BACKEND_API_TOKEN || 'change-me-for-demo'
  return api.post('/api/v1/block', { ip, action, reason }, {
    headers: {
      'X-API-Key': token,
    },
  })
}

export default api
