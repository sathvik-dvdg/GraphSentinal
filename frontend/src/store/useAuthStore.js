// [Windows] GraphSentinel — Susheep
// Auth store — Zustand
//
// Error.md #18/#27: real session auth. login() calls the backend, which
// checks the actual configured operator credentials (secrets.compare_digest,
// not string ==) and returns a real session token — replacing the previous
// version that accepted any non-empty username/password entirely client-side.
import { create } from 'zustand'
import { login as apiLogin, logout as apiLogout, getMe, setSessionToken, clearSessionToken, setUnauthorizedHandler } from '../services/api'

export const SESSION_STORAGE_KEY = 'gs_session_token'
const STORAGE_KEY = SESSION_STORAGE_KEY

const useAuthStore = create((set, get) => ({
  isAuthenticated: false,
  user: null,
  // 'checking' while verifying a token found in sessionStorage on app boot,
  // so a stale/expired token doesn't briefly flash the dashboard before
  // getMe() comes back 401 — ProtectedRoute treats this as "not yet decided."
  authStatus: 'checking', // checking | authenticated | unauthenticated
  loginError: null,

  login: async (username, password) => {
    set({ loginError: null })
    try {
      const res = await apiLogin(username.trim(), password)
      sessionStorage.setItem(STORAGE_KEY, res.token)
      setSessionToken(res.token)
      set({ isAuthenticated: true, user: { username: res.username }, authStatus: 'authenticated' })
      return true
    } catch (err) {
      const detail = err.response?.data?.detail
      const message = err.response?.status === 429
        ? 'Too many attempts — wait a few minutes and try again'
        : detail || 'Login failed — check the backend is reachable'
      set({ loginError: message })
      return false
    }
  },

  logout: async () => {
    await apiLogout()
    sessionStorage.removeItem(STORAGE_KEY)
    clearSessionToken()
    set({ isAuthenticated: false, user: null, authStatus: 'unauthenticated' })
  },

  // Called once on app boot: if a token survived a page refresh, verify it's
  // still valid server-side before trusting it (the backend's session store
  // is in-memory, so it's also empty again after any backend restart).
  checkSession: async () => {
    const token = sessionStorage.getItem(STORAGE_KEY)
    if (!token) {
      set({ authStatus: 'unauthenticated' })
      return
    }
    setSessionToken(token)
    try {
      const res = await getMe()
      set({ isAuthenticated: true, user: { username: res.username }, authStatus: 'authenticated' })
    } catch {
      sessionStorage.removeItem(STORAGE_KEY)
      clearSessionToken()
      set({ isAuthenticated: false, user: null, authStatus: 'unauthenticated' })
    }
  },
}))

// A 401 from any call (not just auth endpoints) means the session is gone —
// expired, revoked, or the backend restarted and forgot its in-memory
// sessions. Force back to a real logged-out state instead of the app
// silently failing every subsequent poll.
setUnauthorizedHandler(() => {
  sessionStorage.removeItem(STORAGE_KEY)
  clearSessionToken()
  useAuthStore.setState({ isAuthenticated: false, user: null, authStatus: 'unauthenticated' })
})

export default useAuthStore
