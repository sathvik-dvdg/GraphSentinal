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

export const getHierarchy = async () => {
  // Mock backend response for now since the backend doesn't serve hierarchy yet.
  return Promise.resolve({
    id: 'root',
    label: 'Root Node',
    sublabel: 'System Server',
    level: 0,
    ip: '10.0.0.1',
    status: 'normal',
    children: [
      {
        id: 'admin',
        label: 'Admin Node',
        sublabel: 'IT / Security Ops',
        level: 1,
        ip: '10.0.0.2',
        status: 'normal',
        children: [
          {
            id: 'finance',
            label: 'Finance Dept',
            sublabel: '8 nodes',
            level: 2,
            ip: '10.0.1.0/24',
            status: 'normal',
            children: [
              {
                id: 'pc-04',
                label: 'PC-04',
                sublabel: '10.0.0.4',
                level: 3,
                ip: '10.0.0.4',
                status: 'normal',
                children: [],
              },
              {
                id: 'pc-07',
                label: 'PC-07',
                sublabel: '10.0.0.7',
                level: 3,
                ip: '10.0.0.7',
                status: 'infected',
                children: [],
              },
            ],
          },
          {
            id: 'dev',
            label: 'Dev Team',
            sublabel: '22 nodes',
            level: 2,
            ip: '10.0.2.0/24',
            status: 'normal',
            children: [
              {
                id: 'pc-11',
                label: 'PC-11',
                sublabel: '10.0.0.11',
                level: 3,
                ip: '10.0.0.11',
                status: 'normal',
                children: [],
              },
            ],
          },
        ],
      },
      {
        id: 'db',
        label: 'DB Node',
        sublabel: 'Database Cluster',
        level: 1,
        ip: '10.0.0.3',
        status: 'normal',
        children: [],
      },
      {
        id: 'core-services',
        label: 'Core Services',
        sublabel: 'Internal APIs',
        level: 1,
        ip: '10.0.0.5',
        status: 'normal',
        children: [],
      },
    ],
  })
}

export const blockIP = (ip, action = 'block', reason = 'MANUAL_OVERRIDE') => {
  const token = import.meta.env.VITE_BACKEND_API_TOKEN || 'change-me-for-demo'
  return api.post('/api/v1/block', { ip, action, reason }, {
    headers: {
      'X-API-Key': token,
    },
  })
}

export const analyzeFlows = (flows) => {
  const token = import.meta.env.VITE_BACKEND_API_TOKEN || 'change-me-for-demo'
  return api.post('/api/v1/analyze', { flows }, {
    headers: { 'X-API-Key': token },
  })
}

export default api
