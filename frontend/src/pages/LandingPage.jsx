import { Navigate } from 'react-router-dom'
import LandingView from '../components/landing/LandingView'
import { useAuth } from '@clerk/react'
import { GS } from '../constants/colors'

export default function LandingPage() {
  // Error.md U8 — a signed-in operator who lands on "/" should go straight to
  // the dashboard instead of the marketing page. Until Clerk has loaded,
  // isSignedIn is undefined, so nothing redirects before the session is known.
  const { isSignedIn } = useAuth()
  if (isSignedIn) {
    return <Navigate to="/dashboard" replace />
  }

  return <LandingView />
}
