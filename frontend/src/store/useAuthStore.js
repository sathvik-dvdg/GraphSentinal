// [Windows] GraphSentinel — Susheep
// Auth store — Zustand, no localStorage
import { create } from 'zustand'

const VALID_CREDENTIALS = [
  { username: 'admin', password: 'graphsentinel2024' },
  { username: 'susheep', password: 'demo123' },
  { username: 'demo', password: 'demo' },
]

const useAuthStore = create((set) => ({
  isAuthenticated: false,
  user: null,

  login: (username, password) => {
    const match = VALID_CREDENTIALS.find(
      (c) => c.username === username && c.password === password
    )
    if (match) {
      set({ isAuthenticated: true, user: { username: match.username } })
      return true
    }
    return false
  },

  logout: () => {
    set({ isAuthenticated: false, user: null })
  },
}))

export default useAuthStore
