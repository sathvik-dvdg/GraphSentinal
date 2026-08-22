// [Windows] GraphSentinel — Susheep
// App.jsx — routing root with ProtectedRoute wrapping AppShell + all sub-routes
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import useAuthStore from './store/useAuthStore'
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
import Settings from './pages/Settings'

function ProtectedRoute({ children }) {
  const { isAuthenticated, authStatus } = useAuthStore()
  // A token can survive a page refresh in sessionStorage — 'checking' covers
  // the round-trip to verify it's still valid server-side, so a stale token
  // doesn't briefly flash the dashboard before an inevitable 401 bounces it
  // back to /login, and a valid one doesn't bounce to /login first either.
  if (authStatus === 'checking') return <LoadingScreen />
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const checkSession = useAuthStore((s) => s.checkSession)

  useEffect(() => {
    checkSession()
  }, [checkSession])

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
            <Route path="dashboard"   element={<DashboardPage />} />
            <Route path="network"     element={<NetworkTopology />} />
            <Route path="threats"     element={<ThreatFeed />} />
            <Route path="forensics"   element={<Forensics />} />
            <Route path="blockchain"  element={<BlockchainLedger />} />
            <Route path="timeline"    element={<TimelineAnalytics />} />
            <Route path="healing"     element={<SelfHealing />} />
            <Route path="alerts"      element={<AlertCentre />} />
            <Route path="settings"    element={<Settings />} />
          </Route>

          {/* Catch-all → landing */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
  )
}
