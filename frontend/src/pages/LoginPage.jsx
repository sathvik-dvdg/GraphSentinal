// [Windows] GraphSentinel — Susheep
import { useNavigate, Link, Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import LoginForm from '../components/auth/LoginForm'
import useAuthStore from '../store/useAuthStore'

// System status lines shown in the terminal panel
const TERMINAL_LINES = [
  { text: 'GRAPHSENTINEL v1.0.0',        cls: 'terminal-heading' },
  { text: '────────────────────────',     cls: 'terminal-divider' },
  { text: '> system status: OPERATIONAL', cls: 'terminal-ok' },
  { text: '> backend: localhost:8000',    cls: 'terminal-dim' },
  { text: '> blockchain: ganache:8545',   cls: 'terminal-dim' },
  { text: '> gnn model: graphsage_v1',    cls: 'terminal-dim' },
  { text: '> active nodes: 10',           cls: 'terminal-dim' },
  { text: '> threat level: ELEVATED',     cls: 'terminal-warn' },
  { text: '────────────────────────',     cls: 'terminal-divider' },
  { text: 'Awaiting operator...',         cls: 'terminal-faint' },
]

export default function LoginPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <div className="login-page">
      {/* Mesh grid background — matches landing page */}
      <div className="login-grid-bg" />

      {/* Subtle radial glow behind form */}
      <div className="login-radial-glow" />

      <div className="login-layout">
        {/* Left Panel — Terminal decoration */}
        <motion.div
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="login-terminal-panel"
        >
          <div className="terminal-window">
            {/* Title bar */}
            <div className="terminal-title-bar">
              <div className="terminal-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>
              <span className="terminal-title-text">graphsentinel — terminal</span>
            </div>

            {/* Terminal content */}
            <div className="terminal-body">
              {TERMINAL_LINES.map((line, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4 + i * 0.08 }}
                  className={`terminal-line ${line.cls}`}
                >
                  {line.text}
                </motion.div>
              ))}
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.4 }}
                className="terminal-cursor blink-cursor"
              >
                █
              </motion.span>
            </div>
          </div>

          {/* Version note */}
          <p className="terminal-footer">
            GraphSentinel · Autonomous Cyber Defense System
          </p>
        </motion.div>

        {/* Right Panel — Login form */}
        <div className="login-form-panel">
          <LoginForm onSuccess={() => navigate('/dashboard')} />

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="login-back-link-wrapper"
          >
            <Link to="/" className="login-back-link">
              ← Back to overview
            </Link>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
