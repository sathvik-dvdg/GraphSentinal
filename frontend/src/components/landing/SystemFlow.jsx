// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'
import { Network, Server, Brain, Shield, Link } from 'lucide-react'

const STAGES = [
  {
    icon: Network,
    title: 'Mininet Network',
    desc: '10-host SDN topology simulating real enterprise traffic',
    owner: 'Sairaj',
    color: '#00ff88',
  },
  {
    icon: Server,
    title: 'FastAPI Backend',
    desc: 'Flow collection, graph construction, and API orchestration',
    owner: 'Sairaj',
    color: '#0099ff',
  },
  {
    icon: Brain,
    title: 'GraphSAGE GNN',
    desc: '3-layer graph neural network with 97.7% accuracy',
    owner: 'Sathvik',
    color: '#ff4444',
  },
  {
    icon: Shield,
    title: 'Self-Healing Engine',
    desc: 'Autonomous node isolation via OVS flow rules',
    owner: 'Sairaj',
    color: '#ffaa00',
  },
  {
    icon: Link,
    title: 'Blockchain Ledger',
    desc: 'Tamper-proof audit trail on local Ganache chain',
    owner: 'Skanda',
    color: '#9945ff',
  },
]

const METRICS = [
  { value: '10', label: 'Virtual Nodes' },
  { value: '5', label: 'Attack Types' },
  { value: '< 5s', label: 'Response Time' },
]

export default function SystemFlow() {
  return (
    <section id="system-flow" className="py-24 px-6 bg-gs-mid relative">
      <div className="max-w-6xl mx-auto">
        {/* Title */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <p className="text-gs-accent text-xs tracking-[0.3em] font-mono mb-3 uppercase">
            System Architecture
          </p>
          <h2 className="text-3xl font-bold text-white">HOW IT WORKS</h2>
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
                  transition={{ delay: i * 0.15 }}
                  whileHover={{ y: -8, borderColor: stage.color }}
                  className="bg-gs-card border border-gs-border rounded-xl p-5 w-48 text-center
                             transition-all duration-300 hover:shadow-lg cursor-default"
                  style={{ '--hover-glow': stage.color }}
                >
                  <div
                    className="w-12 h-12 rounded-lg mx-auto mb-3 flex items-center justify-center"
                    style={{ backgroundColor: `${stage.color}15` }}
                  >
                    <Icon size={24} color={stage.color} />
                  </div>
                  <h3 className="text-sm font-bold text-white mb-2 font-mono">{stage.title}</h3>
                  <p className="text-xs text-gray-500 leading-relaxed mb-2">{stage.desc}</p>
                  <span
                    className="text-xs font-mono px-2 py-0.5 rounded"
                    style={{ color: stage.color, backgroundColor: `${stage.color}15` }}
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
                    transition={{ delay: i * 0.15 + 0.3 }}
                    className="text-gs-accent text-xl font-mono mx-2 hidden lg:block"
                  >
                    →
                  </motion.div>
                )}
              </div>
            )
          })}
        </div>

        {/* Metrics */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.8 }}
          className="flex items-center justify-center gap-12 mt-16"
        >
          {METRICS.map((m, i) => (
            <div key={i} className="text-center">
              <motion.span
                initial={{ scale: 0.5, opacity: 0 }}
                whileInView={{ scale: 1, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 1 + i * 0.2, type: 'spring' }}
                className="text-3xl font-bold text-gs-accent font-mono block"
              >
                {m.value}
              </motion.span>
              <span className="text-xs text-gray-500 font-mono">{m.label}</span>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
