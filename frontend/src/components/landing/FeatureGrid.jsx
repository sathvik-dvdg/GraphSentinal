// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'
import { Brain, Shield, Link, Globe } from 'lucide-react'

const FEATURES = [
  {
    icon: Brain,
    title: 'GraphSAGE Detection',
    body: '3-layer Graph Neural Network trained on CICIDS2017 dataset. Detects DDoS, PortScan, Botnet, SSH Brute Force, DoS Hulk with >92% accuracy and <200ms inference latency.',
    badge: 'F1 ≥ 0.88',
    color: '#ff4444',
  },
  {
    icon: Shield,
    title: 'Autonomous Self-Healing',
    body: 'When threat score exceeds 0.75, the system automatically isolates the malicious node via OVS drop rules. Network stability recovers in under 500ms with zero admin action.',
    badge: '< 500ms',
    color: '#00ff88',
  },
  {
    icon: Link,
    title: 'Immutable Audit Trail',
    body: 'Every incident is fingerprinted with keccak256 and stored on a local Ganache blockchain. Tamper-proof proof-of-existence that survives even if the SQLite log is modified.',
    badge: 'Chain ID: 1337',
    color: '#9945ff',
  },
  {
    icon: Globe,
    title: 'Real-Time 3D Dashboard',
    body: 'Force-directed 3D network graph updates every 5 seconds. Node colors encode threat levels. Animated particles show live traffic flows. Blue wireframe cage appears on isolation.',
    badge: 'WebSocket',
    color: '#0099ff',
  },
]

export default function FeatureGrid() {
  return (
    <section className="py-24 px-6 bg-gs-bg">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <p className="text-gs-accent text-xs tracking-[0.3em] font-mono mb-3 uppercase">
            Core Capabilities
          </p>
          <h2 className="text-3xl font-bold text-white">KEY FEATURES</h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {FEATURES.map((f, i) => {
            const Icon = f.icon
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                whileHover={{ borderColor: f.color, y: -4 }}
                className="bg-gs-card border border-gs-border rounded-xl p-6 transition-all duration-300
                           hover:shadow-lg cursor-default group"
              >
                <div className="flex items-start gap-4">
                  <div
                    className="w-12 h-12 rounded-lg flex-shrink-0 flex items-center justify-center
                               group-hover:scale-110 transition-transform duration-300"
                    style={{ backgroundColor: `${f.color}15` }}
                  >
                    <Icon size={24} color={f.color} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-base font-bold text-white font-mono">{f.title}</h3>
                      <span
                        className="text-xs font-mono px-2 py-0.5 rounded"
                        style={{ color: f.color, backgroundColor: `${f.color}15` }}
                      >
                        {f.badge}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400 leading-relaxed">{f.body}</p>
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
