// [Windows] GraphSentinel — Susheep
import { useState } from 'react'
import { motion } from 'framer-motion'
import useAuthStore from '../../store/useAuthStore'

export default function LoginForm({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!username.trim()) {
      setError('Operator ID required')
      return
    }
    if (!password.trim()) {
      setError('Access code required')
      return
    }

    setLoading(true)

    // Fake 1.5s auth delay for demo effect
    await new Promise((r) => setTimeout(r, 1500))

    const success = login(username.trim(), password)
    if (success) {
      onSuccess()
    } else {
      setError('Authentication failed — invalid credentials')
      setLoading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="bg-gs-card border border-gs-accent/20 rounded-xl p-8 w-full max-w-md"
    >
      {/* Logo */}
      <div className="text-center mb-8">
        <div className="text-4xl mb-3">🛡️</div>
        <h2 className="text-xl font-bold text-white font-mono">GRAPHSENTINEL</h2>
        <p className="text-xs text-gray-500 font-mono tracking-[0.2em] mt-1 uppercase">
          Operator Authentication
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Username */}
        <div>
          <label className="text-xs text-gray-500 font-mono block mb-1.5 uppercase tracking-wider">
            Operator ID
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="admin"
            disabled={loading}
            className="w-full bg-gs-bg border border-gs-border rounded-lg px-4 py-3 text-sm font-mono
                       text-white placeholder-gray-600 outline-none transition-all duration-300
                       focus:border-gs-accent focus:shadow-[0_0_12px_rgba(0,255,136,0.15)]
                       disabled:opacity-50"
          />
        </div>

        {/* Password */}
        <div>
          <label className="text-xs text-gray-500 font-mono block mb-1.5 uppercase tracking-wider">
            Access Code
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
            className="w-full bg-gs-bg border border-gs-border rounded-lg px-4 py-3 text-sm font-mono
                       text-white placeholder-gray-600 outline-none transition-all duration-300
                       focus:border-gs-accent focus:shadow-[0_0_12px_rgba(0,255,136,0.15)]
                       disabled:opacity-50"
          />
        </div>

        {/* Error */}
        {error && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-gs-alert text-xs font-mono"
          >
            ⚠ {error}
          </motion.p>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className={`w-full py-3 rounded-lg font-mono font-bold text-sm transition-all duration-300
            ${
              loading
                ? 'bg-gs-accent/40 text-gs-bg cursor-wait'
                : 'bg-gs-accent text-gs-bg hover:shadow-[0_0_24px_rgba(0,255,136,0.4)] hover:scale-[1.02]'
            }`}
        >
          {loading ? 'Verifying credentials...' : 'AUTHENTICATE →'}
        </button>
      </form>

      {/* Demo hint */}
      <div className="mt-6 pt-4 border-t border-gs-border">
        <p className="text-xs text-gray-600 font-mono text-center">
          Demo credentials:{' '}
          <span className="text-gray-400">admin</span>
          {' / '}
          <span className="text-gray-400">graphsentinel2024</span>
        </p>
      </div>
    </motion.div>
  )
}
