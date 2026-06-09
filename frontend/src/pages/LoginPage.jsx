// [Windows] GraphSentinel — Susheep
import { useNavigate, Link, Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import LoginForm from '../components/auth/LoginForm'
import useAuthStore from '../store/useAuthStore'

const TERMINAL_LINES = [
  'GRAPHSENTINEL SECURITY NODE v1.0.0',
  '─────────────────────────────────',
  '> system status: OPERATIONAL',
  '> backend: localhost:8000 ✓',
  '> blockchain: ganache:8545 ✓',
  '> gnn model: graphsage_v1 ✓',
  '> active nodes: 10',
  '> threat level: ELEVATED',
  '> last incident: 00:02:31 ago',
  '─────────────────────────────────',
  'Awaiting operator authentication...',
]

export default function LoginPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <div className="min-h-screen bg-gs-bg flex hex-bg">
      {/* Left Panel — Terminal decoration (hidden on mobile) */}
      <div className="hidden lg:flex flex-1 items-center justify-center p-12">
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
          className="bg-gs-bg/80 border border-gs-accent/20 rounded-xl p-6 max-w-md w-full font-mono"
        >
          {TERMINAL_LINES.map((line, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 + i * 0.12 }}
              className={`text-sm mb-0.5 ${
                line.startsWith('>')
                  ? 'text-gs-accent'
                  : line.includes('──')
                  ? 'text-gs-accent/40'
                  : line.includes('v1.0.0')
                  ? 'text-white font-bold'
                  : 'text-gray-500'
              }`}
            >
              {line}
            </motion.div>
          ))}
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2.2 }}
            className="text-gs-accent blink-cursor"
          >
            █
          </motion.span>
        </motion.div>
      </div>

      {/* Right Panel — Login form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <LoginForm onSuccess={() => navigate('/dashboard')} />
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1 }}
            className="text-center mt-6"
          >
            <Link
              to="/"
              className="text-xs text-gray-600 font-mono hover:text-gs-accent transition-colors no-underline"
            >
              ← Return to overview
            </Link>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
