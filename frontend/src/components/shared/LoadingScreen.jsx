// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'

export default function LoadingScreen() {
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gs-mesh-bg"
      style={{ backgroundColor: '#0A0A0A' }}
    >
      {/* Subtle ambient glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at 50% 50%, rgba(79,110,247,0.04) 0%, transparent 65%)',
        }}
      />

      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="relative flex flex-col items-center gap-6 z-10"
      >
        {/* Logo mark */}
        <div className="relative w-16 h-16 flex items-center justify-center">
          <motion.div
            className="absolute inset-0 rounded-2xl border border-gs-accent/15"
            animate={{ rotate: 360 }}
            transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
          />
          <motion.div
            className="absolute inset-2 rounded-xl border border-gs-heal/20"
            animate={{ rotate: -360 }}
            transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
          />
          <div className="w-10 h-10 flex items-center justify-center rounded-xl bg-gs-accent-soft border border-gs-accent/25">
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6 text-gs-accent" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
            </svg>
          </div>
        </div>

        {/* Wordmark */}
        <div className="text-center">
          <h1 className="font-heading font-bold text-xl text-gs-text tracking-wide mb-1">
            GraphSentinel
          </h1>
          <p className="text-[11px] text-gs-muted font-mono tracking-widest uppercase">
            Autonomous Cyber Defense
          </p>
        </div>

        {/* Loading dots */}
        <div className="flex items-center gap-2" aria-label="Loading..." role="status">
          {[0, 1, 2, 3, 4].map((i) => (
            <motion.div
              key={i}
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: i % 2 === 0 ? '#4F6EF7' : '#2ECC8A' }}
              animate={{ opacity: [0.2, 1, 0.2], scale: [0.8, 1.2, 0.8] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
            />
          ))}
        </div>

        <p className="text-[11px] text-gs-faint font-mono">
          Initializing defense systems...
        </p>
      </motion.div>

      {/* Version footer */}
      <div className="absolute bottom-6 flex items-center gap-3 z-10">
        <div className="h-px w-10 bg-gs-border" />
        <span className="text-[10px] text-gs-faint font-mono">
          GraphSentinel v1.0.0 · Self-Healing Cyber Defense
        </span>
        <div className="h-px w-10 bg-gs-border" />
      </div>
    </div>
  )
}
