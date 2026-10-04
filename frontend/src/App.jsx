// [Windows] GraphSentinel — Susheep
// App.jsx — routing root with ProtectedRoute wrapping AppShell + all sub-routes
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Show, useAuth } from '@clerk/react'
import api from './services/api'
import SimulationProvider from './providers/SimulationProvider'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import AppShell from './components/layout/AppShell'
import LoadingScreen from './components/shared/LoadingScreen'
import DashboardPage from './pages/DashboardPage'
import NetworkTopology from './pages/NetworkTopology'
import ThreatFeed from './pages/ThreatFeed'
import Forensics from './pages/Forensics'
import BlockchainLedger from './pages/BlockchainLedger'
import TimelineAnalytics from './pages/TimelineAnalytics'
import SelfHealing from './pages/SelfHealing'
import AlertCentre from './pages/AlertCentre'
import AuditLog from './pages/AuditLog'
import Settings from './pages/Settings'

function AxiosInterceptorSetter({ children }) {
  const { getToken } = useAuth()
  
  useEffect(() => {
    const interceptor = api.interceptors.request.use(async (config) => {
      console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`)
      try {
        const token = await getToken()
        if (token && !config.headers.Authorization) {
          config.headers = { ...config.headers, Authorization: `Bearer ${token}` }
        }
      } catch (e) {
        console.warn("Failed to get Clerk token", e)
      }
      return config
    })
    
    return () => {
      api.interceptors.request.eject(interceptor)
    }
  }, [getToken])

  return <>{children}</>
}

function ProtectedRoute({ children }) {
  return (
    <>
      <Show when="signed-in">
        <AxiosInterceptorSetter>
          {children}
        </AxiosInterceptorSetter>
      </Show>
      <Show when="signed-out">
        <Navigate to="/login" replace />
      </Show>
    </>
  )
}

export default function App() {


  return (
    <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Protected app shell wraps all dashboard sub-routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <SimulationProvider>
                  <AppShell />
                </SimulationProvider>
              </ProtectedRoute>
            }
          >
            {/* Error.md U8 / #10 — "/" itself is owned by the public
                LandingPage route above, which now redirects authenticated
                users to /dashboard (see LandingPage.jsx). No index route here
                to avoid two routes matching "/". */}
            <Route path="dashboard"   element={<DashboardPage />} />
            <Route path="network"     element={<NetworkTopology />} />
            <Route path="threats"     element={<ThreatFeed />} />
            <Route path="forensics"   element={<Forensics />} />
            <Route path="blockchain"  element={<BlockchainLedger />} />
            <Route path="timeline"    element={<TimelineAnalytics />} />
            <Route path="healing"     element={<SelfHealing />} />
            <Route path="alerts"      element={<AlertCentre />} />
            <Route path="audit"       element={<AuditLog />} />
            <Route path="settings"    element={<Settings />} />
          </Route>

          {/* Catch-all → landing */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
  )
}
