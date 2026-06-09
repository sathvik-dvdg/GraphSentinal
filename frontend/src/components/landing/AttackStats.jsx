// [Windows] GraphSentinel — Susheep
import { motion } from 'framer-motion'

const ATTACKS = [
  { name: 'DDoS', dataset: 'Friday-Afternoon-DDos.csv', signal: 'Extreme connection_rate', color: '#ff4444' },
  { name: 'PortScan', dataset: 'Friday-Afternoon-PortScan.csv', signal: 'High port_entropy', color: '#ffff00' },
  { name: 'SSHBrute', dataset: 'Tuesday.csv', signal: 'High syn_ratio + port 22', color: '#ff8800' },
  { name: 'Botnet', dataset: 'Friday-Morning.csv', signal: 'byte_asymmetry + C2 ports', color: '#aa44ff' },
  { name: 'DoS Hulk', dataset: 'Wednesday.csv', signal: 'HTTP flood + port 80', color: '#ff2266' },
]

export default function AttackStats() {
  return (
    <section className="py-24 px-6 bg-gs-mid">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <p className="text-gs-accent text-xs tracking-[0.3em] font-mono mb-3 uppercase">
            Threat Intelligence
          </p>
          <h2 className="text-3xl font-bold text-white">ATTACK TYPES DETECTED</h2>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {ATTACKS.map((a, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              whileHover={{ borderColor: a.color, scale: 1.05 }}
              className="bg-gs-card border border-gs-border rounded-xl p-4 text-center
                         transition-all duration-300 cursor-default"
            >
              <div
                className="w-3 h-3 rounded-full mx-auto mb-3"
                style={{ backgroundColor: a.color, boxShadow: `0 0 12px ${a.color}60` }}
              />
              <h3 className="text-sm font-bold font-mono mb-2" style={{ color: a.color }}>
                {a.name}
              </h3>
              <p className="text-xs text-gray-500 mb-1 font-mono">{a.signal}</p>
              <p className="text-xs text-gray-700 font-mono truncate" title={a.dataset}>
                {a.dataset}
              </p>
            </motion.div>
          ))}
        </div>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.6 }}
          className="text-center text-sm text-gray-500 font-mono mt-8"
        >
          Trained on <span className="text-gs-accent">575,000+</span> CICIDS2017 network flow records
        </motion.p>
      </div>
    </section>
  )
}
