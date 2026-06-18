// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'
import { Brain, Shield, Link, Globe } from 'lucide-react'

// ── Original data — untouched ──
const FEATURES = [
  {
    icon: Brain,
    title: 'GraphSAGE Detection',
    body: '3-layer Graph Neural Network trained on CICIDS2017 dataset. Detects DDoS, PortScan, Botnet, SSH Brute Force, DoS Hulk with >92% accuracy and <200ms inference latency.',
    badge: 'F1 ≥ 0.88',
    color: '#f43f5e',
    borderClass: 'border-rose-500/20',
    bgClass: 'bg-rose-500/5',
    badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/25',
  },
  {
    icon: Shield,
    title: 'Autonomous Self-Healing',
    body: 'When threat score exceeds 0.75, the system automatically isolates the malicious node via OVS drop rules. Network stability recovers in under 500ms with zero admin action.',
    badge: '< 500ms',
    color: '#34d399',
    borderClass: 'border-emerald-500/20',
    bgClass: 'bg-emerald-500/5',
    badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25',
  },
  {
    icon: Link,
    title: 'Immutable Audit Trail',
    body: 'Every incident is fingerprinted with keccak256 and stored on a local Ganache blockchain. Tamper-proof proof-of-existence that survives even if the SQLite log is modified.',
    badge: 'Chain ID: 1337',
    color: '#a855f7',
    borderClass: 'border-purple-500/20',
    bgClass: 'bg-purple-500/5',
    badgeClass: 'bg-purple-500/10 text-purple-400 border-purple-500/25',
  },
  {
    icon: Globe,
    title: 'Real-Time 3D Dashboard',
    body: 'Force-directed 3D network graph updates every 5 seconds. Node colors encode threat levels. Animated particles show live traffic flows. Blue wireframe cage appears on isolation.',
    badge: 'WebSocket',
    color: '#06b6d4',
    borderClass: 'border-cyan-500/20',
    bgClass: 'bg-cyan-500/5',
    badgeClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/25',
  },
]

export default function FeatureGrid() {
  return (
    <section id="features" className="py-28 px-6 bg-gs-bg relative overflow-hidden">
      {/* Faint mesh */}
      <div className="absolute inset-0 hex-bg opacity-60 pointer-events-none" />

      {/* Top ambient glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[200px] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(6,182,212,0.05) 0%, transparent 70%)' }} />

      <div className="relative z-10 max-w-6xl mx-auto">

        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <span className="inline-block text-emerald-400 text-[11px] tracking-[0.35em] font-mono mb-4 uppercase px-3 py-1 rounded-full border border-emerald-500/20 bg-emerald-500/5">
            Core Capabilities
          </span>
          <h2 className="font-orbitron text-3xl md:text-4xl font-bold text-white tracking-wide">
            KEY FEATURES
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {FEATURES.map((f, i) => {
            const Icon = f.icon
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                whileHover={{ y: -4 }}
                className={`relative group gs-panel ${f.borderClass} p-6 transition-all duration-300 cursor-default overflow-hidden`}
              >
                {/* Corner accent glow on hover */}
                <div
                  className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-400 pointer-events-none"
                  style={{ boxShadow: `inset 0 0 30px ${f.color}08` }}
                />
                {/* Top-left corner accent line */}
                <div className="absolute top-0 left-0 w-12 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                  style={{ background: `linear-gradient(90deg, ${f.color}, transparent)` }} />
                <div className="absolute top-0 left-0 w-px h-12 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                  style={{ background: `linear-gradient(180deg, ${f.color}, transparent)` }} />

                <div className="flex items-start gap-4 relative z-10">
                  {/* Icon box */}
                  <div
                    className={`w-12 h-12 rounded-xl flex-shrink-0 flex items-center justify-center ${f.bgClass} group-hover:scale-110 transition-transform duration-300`}
                    style={{ border: `1px solid ${f.color}25` }}
                  >
                    <Icon size={22} color={f.color} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <h3 className="text-sm font-bold text-white font-mono">{f.title}</h3>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${f.badgeClass}`}>
                        {f.badge}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500 leading-relaxed">{f.body}</p>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
