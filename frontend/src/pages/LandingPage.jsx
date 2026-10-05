import { Navigate } from 'react-router-dom'
import LandingView from '../components/landing/LandingView'
import useAuthStore from '../store/useAuthStore'
import { GS } from '../constants/colors'

export default function LandingPage() {
  // Error.md U8 — a logged-in operator who lands on "/" should go straight to
  // the dashboard instead of the marketing page. 'checking' falls through so
  // we don't flash a redirect before the session is verified.
  const { isAuthenticated, authStatus } = useAuthStore()
  if (isAuthenticated && authStatus !== 'checking') {
    return <Navigate to="/dashboard" replace />
  }

  return <LandingView />
}
