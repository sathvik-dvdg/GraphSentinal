// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'
import { Network, Server, Brain, Shield, Link } from 'lucide-react'

// ── Original data — untouched ──
const STAGES = [
  {
    icon: Network,
    title: 'Mininet Network',
    desc: '10-host SDN topology simulating real enterprise traffic',
    owner: 'Sairaj',
    color: '#34d399',
    accent: 'emerald',
  },
  {
    icon: Server,
    title: 'FastAPI Backend',
    desc: 'Flow collection, graph construction, and API orchestration',
    owner: 'Sairaj',
    color: '#06b6d4',
    accent: 'cyan',
  },
  {
    icon: Brain,
    title: 'GraphSAGE GNN',
    desc: '3-layer graph neural network with 97.7% accuracy',
    owner: 'Sathvik',
    color: '#f43f5e',
    accent: 'rose',
  },
  {
    icon: Shield,
    title: 'Self-Healing Engine',
    desc: 'Autonomous node isolation via OVS flow rules',
    owner: 'Sairaj',
    color: '#fbbf24',
    accent: 'amber',
  },
  {
    icon: Link,
    title: 'Blockchain Ledger',
    desc: 'Tamper-proof audit trail on local Ganache chain',
    owner: 'Skanda',
    color: '#a855f7',
    accent: 'purple',
  },
]

// ── Original data — untouched ──
const METRICS = [
  { value: '10',   label: 'Virtual Nodes',  color: 'text-cyan-400' },
  { value: '5',    label: 'Attack Types',   color: 'text-rose-400' },
  { value: '< 5s', label: 'Response Time',  color: 'text-emerald-400' },
]

export default function SystemFlow() {
  return (
    <section id="system-flow" className="py-28 px-6 relative overflow-hidden" style={{ background: '#080f1e' }}>
      {/* Subtle mesh grid on section */}
      <div className="absolute inset-0 cyber-grid opacity-50 pointer-events-none" />

      <div className="relative z-10 max-w-6xl mx-auto">

        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-20"
        >
          <span className="inline-block text-cyan-400 text-[11px] tracking-[0.35em] font-mono mb-4 uppercase px-3 py-1 rounded-full border border-cyan-500/20 bg-cyan-500/5">
            System Architecture
          </span>
          <h2 className="font-orbitron text-3xl md:text-4xl font-bold text-white tracking-wide">
            HOW IT WORKS
          </h2>
          <p className="text-slate-500 text-sm font-mono mt-3">
            Five-stage autonomous pipeline from packet ingestion to blockchain audit
          </p>
        </motion.div>

        {/* Pipeline stages */}
        <div className="flex flex-wrap items-start justify-center gap-4">
          {STAGES.map((stage, i) => {
            const Icon = stage.icon
            return (
              <div key={i} className="flex items-center">
                <motion.div
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.12 }}
                  whileHover={{ y: -6, borderColor: stage.color }}
                  className="relative group gs-panel corner-tl corner-br w-48 text-center p-5 cursor-default transition-all duration-300 hover:shadow-panel"
                  style={{ borderColor: `${stage.color}20` }}
                >
                  {/* Glow on hover */}
                  <div
                    className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                    style={{ boxShadow: `0 0 24px ${stage.color}20, inset 0 0 24px ${stage.color}05` }}
                  />

                  {/* Stage number */}
                  <div
                    className="absolute -top-2.5 left-1/2 -translate-x-1/2 text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border"
                    style={{ color: stage.color, borderColor: `${stage.color}40`, background: `${stage.color}10` }}
                  >
                    STEP {String(i + 1).padStart(2, '0')}
                  </div>

                  {/* Icon */}
                  <div
                    className="w-12 h-12 rounded-xl mx-auto mb-3 mt-2 flex items-center justify-center group-hover:scale-110 transition-transform duration-300"
                    style={{ backgroundColor: `${stage.color}12`, border: `1px solid ${stage.color}30` }}
                  >
                    <Icon size={22} color={stage.color} />
                  </div>

                  <h3 className="text-sm font-bold text-white mb-1.5 font-mono leading-tight">
                    {stage.title}
                  </h3>
                  <p className="text-[11px] text-slate-500 leading-relaxed mb-3">{stage.desc}</p>
                  <span
                    className="text-[10px] font-mono px-2 py-0.5 rounded-full border"
                    style={{ color: stage.color, borderColor: `${stage.color}30`, background: `${stage.color}10` }}
                  >
                    {stage.owner}
                  </span>
                </motion.div>

                {/* Arrow connector */}
                {i < STAGES.length - 1 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.12 + 0.3 }}
                    className="text-cyan-500/50 text-xl font-mono mx-2 hidden lg:flex flex-col items-center gap-1"
                  >
                    <div className="w-6 h-px bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent" />
                    <span className="text-xs text-cyan-500/40">→</span>
                    <div className="w-6 h-px bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent" />
                  </motion.div>
                )}
              </div>
            )
          })}
        </div>

        {/* Metrics row */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.8 }}
          className="flex items-center justify-center gap-16 mt-20"
        >
          {METRICS.map((m, i) => (
            <div key={i} className="text-center relative group">
              {/* Glow backdrop */}
              <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{ background: 'radial-gradient(circle, rgba(6,182,212,0.06) 0%, transparent 70%)' }} />
              <motion.span
                initial={{ scale: 0.5, opacity: 0 }}
                whileInView={{ scale: 1, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 1 + i * 0.2, type: 'spring' }}
                className={`font-orbitron text-4xl font-black ${m.color} block mb-1`}
              >
                {m.value}
              </motion.span>
              <span className="text-[11px] text-slate-500 font-mono tracking-widest uppercase">
                {m.label}
              </span>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
