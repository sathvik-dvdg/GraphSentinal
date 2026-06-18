// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'

// ── Original data — untouched ──
const ATTACKS = [
  { name: 'DDoS',     dataset: 'Friday-Afternoon-DDos.csv',     signal: 'Extreme connection_rate',     color: '#f43f5e', ring: 'border-rose-500/30',   bg: 'bg-rose-500/5'   },
  { name: 'PortScan', dataset: 'Friday-Afternoon-PortScan.csv', signal: 'High port_entropy',           color: '#fbbf24', ring: 'border-amber-500/30',  bg: 'bg-amber-500/5'  },
  { name: 'SSHBrute', dataset: 'Tuesday.csv',                   signal: 'High syn_ratio + port 22',   color: '#f97316', ring: 'border-orange-500/30', bg: 'bg-orange-500/5' },
  { name: 'Botnet',   dataset: 'Friday-Morning.csv',            signal: 'byte_asymmetry + C2 ports',  color: '#a855f7', ring: 'border-purple-500/30', bg: 'bg-purple-500/5' },
  { name: 'DoS Hulk', dataset: 'Wednesday.csv',                 signal: 'HTTP flood + port 80',       color: '#ec4899', ring: 'border-pink-500/30',   bg: 'bg-pink-500/5'   },
]

export default function AttackStats() {
  return (
    <section className="py-28 px-6 relative overflow-hidden" style={{ background: '#080f1e' }}>
      <div className="absolute inset-0 cyber-grid opacity-40 pointer-events-none" />

      <div className="relative z-10 max-w-6xl mx-auto">

        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <span className="inline-block text-rose-400 text-[11px] tracking-[0.35em] font-mono mb-4 uppercase px-3 py-1 rounded-full border border-rose-500/20 bg-rose-500/5">
            Threat Intelligence
          </span>
          <h2 className="font-orbitron text-3xl md:text-4xl font-bold text-white tracking-wide">
            ATTACK TYPES DETECTED
          </h2>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {ATTACKS.map((a, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              whileHover={{ scale: 1.05, y: -4 }}
              className={`relative group gs-panel ${a.ring} ${a.bg} p-5 text-center cursor-default transition-all duration-300 overflow-hidden`}
            >
              {/* Glow overlay */}
              <div
                className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                style={{ boxShadow: `inset 0 0 24px ${a.color}10` }}
              />

              {/* Pulsing threat dot */}
              <div className="relative mx-auto mb-4 w-10 h-10 flex items-center justify-center">
                <div
                  className="absolute w-10 h-10 rounded-full animate-pulse opacity-20"
                  style={{ backgroundColor: a.color }}
                />
                <div
                  className="w-4 h-4 rounded-full"
                  style={{ backgroundColor: a.color, boxShadow: `0 0 14px ${a.color}80` }}
                />
              </div>

              {/* Name */}
              <h3 className="text-sm font-bold font-mono mb-2" style={{ color: a.color }}>
                {a.name}
              </h3>

              {/* Signal */}
              <p className="text-[10px] text-slate-500 font-mono mb-2 leading-relaxed">{a.signal}</p>

              {/* Dataset badge */}
              <div
                className="text-[9px] font-mono truncate px-2 py-1 rounded-md border"
                style={{ color: `${a.color}90`, borderColor: `${a.color}20`, background: `${a.color}08` }}
                title={a.dataset}
              >
                {a.dataset}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Bottom stat line */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.6 }}
          className="text-center mt-10 flex items-center justify-center gap-3"
        >
          <div className="h-px w-16 bg-gradient-to-r from-transparent to-slate-700" />
          <p className="text-sm text-slate-500 font-mono">
            Trained on{' '}
            <span className="text-emerald-400 font-bold">575,000+</span>{' '}
            CICIDS2017 network flow records
          </p>
          <div className="h-px w-16 bg-gradient-to-l from-transparent to-slate-700" />
        </motion.div>
      </div>
    </section>
  )
}
