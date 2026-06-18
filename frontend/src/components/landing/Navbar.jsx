// [Windows] GraphSentinel — Susheep
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

export default function Navbar() {
  return (
    <motion.nav
      initial={{ y: -60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.7, ease: 'easeOut' }}
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3.5 border-b border-surface-container-highest"
      style={{ background: 'rgba(5,20,36,0.88)', backdropFilter: 'blur(16px)' }}
    >
      {/* Logo */}
      <Link to="/" className="flex items-center gap-3 no-underline group">
        {/* Animated shield icon */}
        <div className="relative w-8 h-8 flex items-center justify-center">
          <div className="absolute inset-0 rounded-md bg-primary-container/10 border border-primary-container/30 group-hover:border-primary-container/60 transition-colors duration-300" />
          <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 text-primary-container" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
          </svg>
        </div>
        <div className="flex flex-col -space-y-0.5">
          <span className="font-geist text-primary-container font-bold text-sm tracking-widest uppercase glow-primary">
            GRAPHSENTINEL
          </span>
          <span className="text-slate-500 text-[9px] font-mono tracking-[0.25em] uppercase">
            Cyber Defense AI
          </span>
        </div>
      </Link>

      {/* Center Nav Links */}
      <div className="hidden md:flex items-center gap-8 absolute left-1/2 -translate-x-1/2">
        <a
          href="#system-flow"
          className="text-on-surface-variant hover:text-primary-container text-xs font-mono tracking-widest uppercase transition-colors duration-200 no-underline"
        >
          Architecture
        </a>
        <a
          href="#features"
          className="text-on-surface-variant hover:text-primary-container text-xs font-mono tracking-widest uppercase transition-colors duration-200 no-underline"
        >
          Features
        </a>
      </div>

      {/* Right action */}
      <div className="flex items-center">
        <Link
          to="/login"
          className="tac-btn neon-cta relative px-5 py-2 bg-primary-container/10 border border-primary-container/60 text-primary-container rounded-soft font-mono text-xs tracking-wider uppercase no-underline hover:bg-primary-container/20 hover:border-primary-container hover:shadow-glow-primary transition-all duration-300"
        >
          ENTER SYSTEM →
        </Link>
      </div>
    </motion.nav>
  )
}
