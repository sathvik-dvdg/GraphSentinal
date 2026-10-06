// [Windows] GraphSentinel — Susheep
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { SignIn } from '@clerk/react'

// Decorative terminal panel. FE-23 — it used to print a fixed "system status:
// OPERATIONAL", "threat level: ELEVATED", "active nodes: 10" and
// "backend: localhost:8000", which read as live status but never changed. The
// live state is on the dashboard after sign-in.
const TERMINAL_LINES = [
  { text: 'GRAPHSENTINEL v1.0.0',        cls: 'terminal-heading' },
  { text: '────────────────────────',     cls: 'terminal-divider' },
  { text: '> graph-based threat detection', cls: 'terminal-dim' },
  { text: '> self-healing enforcement',     cls: 'terminal-dim' },
  { text: '> blockchain audit trail',       cls: 'terminal-dim' },
  { text: '────────────────────────',     cls: 'terminal-divider' },
  { text: 'Sign in to see live status...', cls: 'terminal-faint' },
]

export default function LoginPage() {


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
          <div style={{ display: 'flex', justifyContent: 'center', width: '100%' }}>
            <SignIn forceRedirectUrl="/dashboard" />
          </div>

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
