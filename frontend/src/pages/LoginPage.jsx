// [Windows] GraphSentinel — Susheep
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { SignIn, SignUp } from '@clerk/react'

// The left panel says what the system does in the landing page's own words and
// type. FE-23 — it must not print status that reads as live (it once showed a fixed
// "system status: OPERATIONAL"); the live state is on the dashboard after sign-in.
const POINTS = ['Graph-based threat detection', 'Self-healing enforcement', 'Blockchain audit trail']

export default function LoginPage({ mode = 'sign-in' }) {
  const register = mode === 'sign-up'
  return (
    <div className="login-page">
      <div className="login-layout">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="login-intro"
        >
          <Link to="/" className="login-wordmark">GraphSentinel</Link>
          <p className="login-lede">
            A graph neural network detects the attack, the network isolates the node, and a local chain keeps the record.
          </p>
          <ul className="login-points">
            {POINTS.map((point) => <li key={point}>{point}</li>)}
          </ul>
          <p className="login-note">
            {register ? 'New accounts start without a role. An administrator grants access after you register.' : 'Sign in to see live status.'}
          </p>
        </motion.div>

        <div className="login-form-panel">
          <div style={{ display: 'flex', justifyContent: 'center', width: '100%' }}>
            {register
              ? <SignUp routing="path" path="/register" signInUrl="/login" forceRedirectUrl="/dashboard" />
              : <SignIn routing="path" path="/login" signUpUrl="/register" forceRedirectUrl="/dashboard" />}
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="login-back-link-wrapper"
          >
            <Link to={register ? '/login' : '/register'} className="login-back-link">
              {register ? 'Already have an account? Sign in' : 'No account yet? Register'}
            </Link>
            <span className="login-back-sep" aria-hidden="true">·</span>
            <Link to="/" className="login-back-link">Back to overview</Link>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
