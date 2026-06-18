// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'

export default function LoadingScreen() {
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center cyber-grid" style={{ background: '#020817' }}>
      {/* Ambient glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 50%, rgba(6,182,212,0.06) 0%, transparent 65%)' }}
      />

      {/* ── Original animation logic preserved ── */}
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="relative flex flex-col items-center gap-6 z-10"
      >
        {/* Logo */}
        <div className="relative w-20 h-20 flex items-center justify-center">
          {/* Outer ring */}
          <motion.div
            className="absolute inset-0 rounded-2xl border border-cyan-500/20"
            animate={{ rotate: 360 }}
            transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
          />
          {/* Inner ring */}
          <motion.div
            className="absolute inset-2 rounded-xl border border-emerald-500/30"
            animate={{ rotate: -360 }}
            transition={{ duration: 5, repeat: Infinity, ease: 'linear' }}
          />
          {/* Shield icon */}
          <div className="w-12 h-12 flex items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/30">
            <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 text-emerald-400" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
            </svg>
          </div>
        </div>

        {/* Heading */}
        <div className="text-center">
          <h1 className="font-orbitron text-2xl font-black text-white tracking-widest mb-1 glow-emerald" style={{ color: '#34d399' }}>
            GRAPHSENTINEL
          </h1>
          <p className="text-[10px] text-slate-600 font-mono tracking-[0.3em] uppercase">
            Autonomous Cyber Defense
          </p>
        </div>

        {/* Loading dots — original animate values preserved */}
        <div className="flex items-center gap-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <motion.div
              key={i}
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: i % 2 === 0 ? '#34d399' : '#06b6d4' }}
              animate={{ opacity: [0.2, 1, 0.2], scale: [0.8, 1.3, 0.8] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
            />
          ))}
        </div>

        {/* Status text */}
        <p className="text-[11px] text-slate-600 font-mono">
          Initializing defense systems...
        </p>
      </motion.div>

      {/* Version footer */}
      <div className="absolute bottom-8 flex items-center gap-2 z-10">
        <div className="h-px w-12 bg-gradient-to-r from-transparent to-slate-800" />
        <span className="text-[10px] text-slate-800 font-mono">
          GraphSentinel v1.0.0 · Self-Healing Cyber Defense
        </span>
        <div className="h-px w-12 bg-gradient-to-l from-transparent to-slate-800" />
      </div>
    </div>
  )
}
