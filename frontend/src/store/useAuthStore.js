// [Windows] GraphSentinel — Susheep
// Auth store — Zustand, no localStorage
import { create } from "zustand";

const useAuthStore = create((set) => ({
  isAuthenticated: false,
  user: null,

  login: (username, password) => {
    if (!username.trim() || !password.trim()) {
      return false;
    }

    set({ isAuthenticated: true, user: { username: username.trim() } });
    return true;
  },

  logout: () => {
    set({ isAuthenticated: false, user: null });
  },
}));

export default useAuthStore;
