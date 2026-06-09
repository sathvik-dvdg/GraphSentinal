// [Windows] GraphSentinel — Susheep
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'

const TERMINAL_LINES = [
  '> Mininet topology: 10 nodes active',
  '> GraphSAGE GNN: threat detection online',
  '> Self-healing engine: armed',
  '> Blockchain ledger: Ganache local chain connected',
  '> System status: OPERATIONAL',
]

export default function HeroSection() {
  const [visibleLines, setVisibleLines] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setVisibleLines((prev) => {
        if (prev >= TERMINAL_LINES.length) {
          clearInterval(timer)
          return prev
        }
        return prev + 1
      })
    }, 600)
    return () => clearInterval(timer)
  }, [])

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden cyber-grid">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(6)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute rounded-full"
            style={{
              width: `${80 + i * 60}px`,
              height: `${80 + i * 60}px`,
              border: '1px solid rgba(0, 255, 136, 0.06)',
              left: `${60 + i * 5}%`,
              top: `${20 + i * 10}%`,
            }}
            animate={{
              rotate: [0, 360],
              scale: [1, 1.05, 1],
            }}
            transition={{
              rotate: { duration: 20 + i * 5, repeat: Infinity, ease: 'linear' },
              scale: { duration: 4, repeat: Infinity, delay: i * 0.5 },
            }}
          />
        ))}
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 text-center">
        {/* Eyebrow */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="text-gs-accent text-xs tracking-[0.3em] font-mono mb-6 uppercase"
        >
          Major Project — Cyber Defense AI
        </motion.p>

        {/* Main heading */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.8 }}
          className="text-6xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-gs-accent to-white bg-clip-text text-transparent"
          style={{ backgroundSize: '200% auto', animation: 'gradient-shift 4s ease infinite' }}
        >
          GraphSentinel
        </motion.h1>

        {/* Tagline */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="text-lg md:text-xl text-gray-400 max-w-3xl mx-auto mb-10 leading-relaxed"
        >
          Self-Healing Cyber Defense using Graph Deep Learning
          <br />& Immutable Audit Trails
        </motion.p>

        {/* Terminal box */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1 }}
          className="mx-auto max-w-lg bg-gs-bg/80 border border-gs-accent/30 rounded-lg p-4 mb-10 text-left"
        >
          <div className="flex items-center gap-2 mb-3 border-b border-gs-accent/20 pb-2">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
            <span className="text-xs text-gray-600 ml-2 font-mono">graphsentinel-terminal</span>
          </div>
          {TERMINAL_LINES.map((line, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={i < visibleLines ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.3 }}
              className="text-gs-accent text-sm font-mono mb-1"
            >
              {line}
              {i === visibleLines - 1 && (
                <span className="blink-cursor ml-0.5 text-gs-accent">█</span>
              )}
            </motion.div>
          ))}
          {visibleLines === 0 && (
            <span className="blink-cursor text-gs-accent text-sm font-mono">█</span>
          )}
        </motion.div>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.4 }}
          className="flex items-center justify-center gap-4"
        >
          <Link
            to="/login"
            className="bg-gs-accent text-gs-bg px-8 py-3 rounded-lg font-mono font-bold text-sm
                       hover:shadow-[0_0_30px_rgba(0,255,136,0.4)] transition-all duration-300 no-underline
                       hover:scale-105"
          >
            ENTER SYSTEM
          </Link>
          <a
            href="#system-flow"
            className="border border-gray-600 text-gray-400 px-8 py-3 rounded-lg font-mono text-sm
                       hover:border-gs-accent hover:text-gs-accent transition-all duration-300 no-underline"
          >
            VIEW DEMO ↓
          </a>
        </motion.div>
      </div>

      {/* Bottom gradient fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-gs-mid to-transparent pointer-events-none" />
    </section>
  )
}
