// [Windows] GraphSentinel — Susheep
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

export default function Navbar() {
  return (
    <motion.nav
      initial={{ y: -60 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4"
      style={{ background: 'rgba(10, 14, 26, 0.92)', backdropFilter: 'blur(12px)' }}
    >
      <Link to="/" className="flex items-center gap-2 no-underline">
        <span className="text-2xl">🛡️</span>
        <span className="text-gs-accent font-bold text-lg font-mono tracking-wider">
          SAIRAJ GANDU
        </span>
      </Link>

      <Link
        to="/login"
        className="border border-gs-accent text-gs-accent px-5 py-2 rounded-lg font-mono text-sm
                   hover:bg-gs-accent hover:text-gs-bg transition-all duration-300 no-underline
                   hover:shadow-[0_0_20px_rgba(0,255,136,0.3)]"
      >
        ENTER SYSTEM →
      </Link>
    </motion.nav>
  )
}
