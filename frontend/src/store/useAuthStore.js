// [Windows] GraphSentinel — Susheep
// Auth store — Zustand, no localStorage
//
// § 4.1 NOTE: This is a LOCAL DEMO ACCESS GATE, not production authentication.
// There is no real backend auth system (API-key only, no user auth).
// The login() function accepts any non-empty username/password — this is by design.
// The UI makes this explicit to operators. Do not add logic here that implies
// real credential verification without a corresponding backend endpoint.
import { create } from 'zustand'

const useAuthStore = create((set) => ({
  isAuthenticated: false,
  user: null,

  /**
   * Local demo gate — accepts any non-empty credentials.
   * This grants access to the dashboard for local/demo use only.
   * Not production auth.
   */
  login: (username, password) => {
    if (!username.trim() || !password.trim()) {
      return false
    }
    set({ isAuthenticated: true, user: { username: username.trim() } })
    return true
  },

  logout: () => {
    set({ isAuthenticated: false, user: null })
  },
}))

export default useAuthStore
