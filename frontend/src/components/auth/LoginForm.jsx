// [Windows] GraphSentinel — Susheep
// Error.md #18/#27: real backend login (secrets.compare_digest against the
// configured operator credentials), not a client-side "any input works" gate.
import { useState } from 'react'
import { motion } from 'framer-motion'
import useAuthStore from '../../store/useAuthStore'

export default function LoginForm({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const { login, loginError } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return

    setLoading(true)
    const success = await login(username, password)
    setLoading(false)
    if (success) onSuccess()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.4 }}
      className="login-form-container"
    >
      {/* Header */}
      <div className="login-header">
        <div className="login-brand">
          <div className="login-brand-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
            </svg>
          </div>
          <div>
            <h1 className="login-brand-name">GraphSentinel</h1>
            <p className="login-brand-sub">Dashboard Access</p>
          </div>
        </div>

        <h2 className="login-title">Enter Dashboard</h2>
        <p className="login-subtitle">
          Sign in to access the monitoring console.
        </p>
      </div>

      {/* Still a single shared operator credential, not multi-user/SSO —
          but now a real one, checked server-side, not "anything works." */}
      <div className="login-demo-notice">
        <span className="login-demo-icon">◆</span>
        <p className="login-demo-text">
          <span className="login-demo-label">SINGLE OPERATOR</span>
          {' '}— One shared credential, checked by the backend. No per-user accounts or roles yet.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="login-form" id="login-form">
        {/* Username */}
        <div className="login-field">
          <label htmlFor="login-username" className="login-label">
            Username
          </label>
          <input
            id="login-username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="admin"
            disabled={loading}
            autoComplete="username"
            className="login-input"
          />
        </div>

        {/* Password */}
        <div className="login-field">
          <label htmlFor="login-password" className="login-label">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
            autoComplete="current-password"
            className="login-input"
          />
        </div>

        {/* Error — real backend response, not a client-side guess */}
        {loginError && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="login-error"
            role="alert"
          >
            <span>▲</span> {loginError}
          </motion.p>
        )}

        {/* Submit */}
        <button
          id="login-submit"
          type="submit"
          disabled={loading}
          className="login-submit-btn"
        >
          {loading ? (
            <span className="login-loading">
              <svg className="spin-slow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
              Opening...
            </span>
          ) : 'Open Dashboard →'}
        </button>
      </form>
    </motion.div>
  )
}
