import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Network, Server, Brain, Shield, Link2, Globe } from 'lucide-react'
import Navbar from '../components/landing/Navbar'
import Footer from '../components/landing/Footer'

const PIPELINE_STAGES = [
  {
    step: '01',
    icon: Network,
    title: 'Mininet Network',
    desc: '10-host SDN topology simulating real enterprise traffic patterns',
    color: '#12a672',
    owner: 'Sairaj',
  },
  {
    step: '02',
    icon: Server,
    title: 'FastAPI Backend',
    desc: 'Flow collection, graph construction, and API orchestration',
    color: '#3b56d9',
    owner: 'Sairaj',
  },
  {
    step: '03',
    icon: Brain,
    title: 'GraphSAGE GNN',
    desc: '3-layer graph neural network with 97.7% detection accuracy',
    color: '#E03C3C',
    owner: 'Sathvik',
  },
  {
    step: '04',
    icon: Shield,
    title: 'Self-Healing Engine',
    desc: 'Autonomous node isolation via OVS flow rules in under 500ms',
    color: '#b7791f',
    owner: 'Sairaj',
  },
  {
    step: '05',
    icon: Link2,
    title: 'Blockchain Ledger',
    desc: 'Tamper-proof keccak256 audit trail on local Ganache chain',
    color: '#7c3aed',
    owner: 'Skanda',
  },
]

const CAPABILITIES = [
  {
    icon: Brain,
    title: 'GraphSAGE Detection',
    body: '3-layer Graph Neural Network trained on CICIDS2017 dataset. Detects DDoS, PortScan, Botnet, SSH Brute Force, DoS Hulk with >92% accuracy and <200ms inference latency.',
    badge: 'F1 >= 0.88',
    color: '#E03C3C',
  },
  {
    icon: Shield,
    title: 'Autonomous Self-Healing',
    body: 'When threat score exceeds 0.75, the system automatically isolates the malicious node via OVS drop rules. Network stability recovers in under 500ms with zero admin action.',
    badge: '< 500ms',
    color: '#12a672',
  },
  {
    icon: Link2,
    title: 'Immutable Audit Trail',
    body: 'Every incident is fingerprinted with keccak256 and stored on a local Ganache blockchain. Tamper-proof proof-of-existence that survives even if the SQLite log is modified.',
    badge: 'Chain ID: 1337',
    color: '#7c3aed',
  },
  {
    icon: Globe,
    title: 'Real-Time Dashboard',
    body: 'Force-directed network graph updates every 5 seconds via WebSocket. Node shapes encode threat levels. Animated particles show live traffic flows.',
    badge: 'WebSocket',
    color: '#3b56d9',
  },
]

const ATTACK_TYPES = [
  { name: 'DDoS', signal: 'Extreme connection_rate', dataset: 'Friday-DDos.csv', color: '#E03C3C' },
  { name: 'PortScan', signal: 'High port_entropy', dataset: 'Friday-PortScan.csv', color: '#b7791f' },
  { name: 'SSHBrute', signal: 'High syn_ratio + port 22', dataset: 'Tuesday.csv', color: '#a16207' },
  { name: 'Botnet', signal: 'byte_asymmetry + C2 ports', dataset: 'Friday-Morning.csv', color: '#7c3aed' },
  { name: 'DoS Hulk', signal: 'HTTP flood + port 80', dataset: 'Wednesday.csv', color: '#EC4899' },
]

const METRICS = [
  { value: '10', label: 'Virtual Nodes', color: '#3b56d9' },
  { value: '5', label: 'Attack Types', color: '#E03C3C' },
  { value: '< 5s', label: 'Response Time', color: '#12a672' },
  { value: '97.7%', label: 'GNN Accuracy', color: '#7c3aed' },
]

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
}

export default function LandingPage() {
  return (
    <div
      className="antialiased min-h-screen flex flex-col"
      style={{ backgroundColor: '#f4f6f8', color: '#1b1f27' }}
    >
      <div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          backgroundImage:
            'linear-gradient(rgba(79,110,247,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(79,110,247,0.02) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <Navbar />

      <main className="flex-grow z-10 pt-14 sm:pt-16">
        <section
          id="hero"
          className="relative w-full flex flex-col items-center text-center px-5 sm:px-6 pt-20 sm:pt-24 md:pt-28 pb-20 sm:pb-24 md:pb-28 max-w-5xl mx-auto"
        >
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.4 }}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-gs-heal/25 bg-gs-heal-soft mb-6 sm:mb-8"
          >
            <motion.span
              className="w-1.5 h-1.5 rounded-full bg-gs-heal"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.8, repeat: Infinity }}
            />
            <span className="text-gs-heal text-[11px] font-mono tracking-wider uppercase">
              System Status: Operational
            </span>
          </motion.div>

          <motion.h1
            {...fadeUp}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="max-w-4xl text-3xl sm:text-5xl md:text-6xl font-heading font-bold text-gs-text leading-[1.05] tracking-tight mb-4 sm:mb-5"
          >
            Network Intelligence,
            <br />
            <span className="text-gs-accent">Autonomously Defended.</span>
          </motion.h1>

          <motion.p
            {...fadeUp}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-sm sm:text-base md:text-lg text-gs-muted max-w-2xl leading-relaxed mb-8 sm:mb-10"
          >
            GraphSentinel uses a 3-layer Graph Neural Network to detect attacks in real time,
            auto-isolate malicious nodes, and record every incident on an immutable blockchain ledger -
            with zero human intervention.
          </motion.p>

          <motion.div
            {...fadeUp}
            transition={{ duration: 0.4, delay: 0.3 }}
            className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full sm:w-auto"
          >
            <Link
              to="/login"
              id="hero-cta-dashboard"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-gs-heal text-white font-heading font-semibold text-sm hover:bg-gs-heal/90 transition-colors duration-200 no-underline w-full sm:w-auto"
            >
              Open Dashboard -&gt;
            </Link>
            <a
              href="#pipeline"
              id="hero-cta-architecture"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg border border-gs-border text-gs-muted font-heading font-medium text-sm hover:border-gs-heal/40 hover:text-gs-text transition-all duration-200 no-underline w-full sm:w-auto"
            >
              View Architecture
            </a>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.5 }}
            className="grid grid-cols-2 sm:flex items-center gap-x-8 gap-y-6 md:gap-14 mt-12 sm:mt-16 pt-8 sm:pt-10 border-t border-gs-border w-full justify-center"
          >
            {METRICS.map((metric) => (
              <div key={metric.label} className="text-center">
                <div
                  className="text-3xl font-heading font-bold tabular-nums mb-1"
                  style={{ color: metric.color }}
                >
                  {metric.value}
                </div>
                <div className="text-[11px] text-gs-muted font-mono uppercase tracking-widest">
                  {metric.label}
                </div>
              </div>
            ))}
          </motion.div>
        </section>

        <section
          id="pipeline"
          className="py-16 sm:py-20 px-5 sm:px-6 border-t border-gs-border"
          style={{ backgroundColor: '#ffffff' }}
        >
          <div className="w-full max-w-6xl mx-auto">
            <motion.div {...fadeUp} className="text-center mb-14">
              <span className="inline-block text-gs-accent text-[11px] font-mono tracking-widest uppercase px-3 py-1 rounded-full border border-gs-accent/20 bg-gs-accent-soft mb-4">
                System Architecture
              </span>
              <h2 className="text-2xl md:text-3xl font-heading font-bold text-gs-text mb-3">
                How It Works
              </h2>
              <p className="text-gs-muted text-sm max-w-md mx-auto">
                Five-stage autonomous pipeline from packet ingestion to blockchain audit
              </p>
            </motion.div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
              {PIPELINE_STAGES.map((stage, index) => {
                const Icon = stage.icon
                return (
                  <motion.div
                    key={stage.step}
                    {...fadeUp}
                    transition={{ delay: index * 0.1 }}
                    whileHover={{ y: -4 }}
                    className="gs-panel p-5 text-center cursor-default transition-all duration-300 hover:border-opacity-60 min-h-full"
                    style={{ borderColor: `${stage.color}25` }}
                  >
                    <div
                      className="text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border inline-block mb-3"
                      style={{ color: stage.color, borderColor: `${stage.color}30`, background: `${stage.color}10` }}
                    >
                      STEP {stage.step}
                    </div>

                    <div
                      className="w-10 h-10 rounded-xl mx-auto mb-3 flex items-center justify-center"
                      style={{ background: `${stage.color}12`, border: `1px solid ${stage.color}25` }}
                    >
                      <Icon size={20} color={stage.color} />
                    </div>

                    <h3 className="text-[13px] font-heading font-semibold text-gs-text mb-1.5 leading-tight">
                      {stage.title}
                    </h3>
                    <p className="text-[11px] text-gs-muted leading-relaxed mb-3">
                      {stage.desc}
                    </p>
                    <span
                      className="text-[10px] font-mono px-2 py-0.5 rounded-full border"
                      style={{ color: stage.color, borderColor: `${stage.color}25`, background: `${stage.color}08` }}
                    >
                      {stage.owner}
                    </span>
                  </motion.div>
                )
              })}
            </div>
          </div>
        </section>

        <section id="capabilities" className="py-16 sm:py-20 px-5 sm:px-6 border-t border-gs-border">
          <div className="w-full max-w-5xl mx-auto">
            <motion.div {...fadeUp} className="text-center mb-12">
              <span className="inline-block text-gs-heal text-[11px] font-mono tracking-widest uppercase px-3 py-1 rounded-full border border-gs-heal/20 bg-gs-heal-soft mb-4">
                Core Capabilities
              </span>
              <h2 className="text-2xl md:text-3xl font-heading font-bold text-gs-text">
                Built for Real Threats
              </h2>
            </motion.div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {CAPABILITIES.map((capability, index) => {
                const Icon = capability.icon
                return (
                  <motion.div
                    key={capability.title}
                    {...fadeUp}
                    transition={{ delay: index * 0.08 }}
                    whileHover={{ y: -3 }}
                    className="gs-panel p-6 transition-all duration-200 hover:border-opacity-40"
                    style={{ borderColor: `${capability.color}20` }}
                  >
                    <div className="flex items-start gap-4">
                      <div
                        className="w-10 h-10 rounded-xl flex-shrink-0 flex items-center justify-center"
                        style={{ background: `${capability.color}12`, border: `1px solid ${capability.color}20` }}
                      >
                        <Icon size={20} color={capability.color} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <h3 className="text-sm font-heading font-semibold text-gs-text">
                            {capability.title}
                          </h3>
                          <span
                            className="text-[10px] font-mono px-2 py-0.5 rounded-md border"
                            style={{ color: capability.color, borderColor: `${capability.color}25`, background: `${capability.color}08` }}
                          >
                            {capability.badge}
                          </span>
                        </div>
                        <p className="text-sm text-gs-muted leading-relaxed">{capability.body}</p>
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </div>
        </section>

        <section
          id="threats"
          className="py-16 sm:py-20 px-5 sm:px-6 border-t border-gs-border"
          style={{ backgroundColor: '#ffffff' }}
        >
          <div className="w-full max-w-5xl mx-auto">
            <motion.div {...fadeUp} className="text-center mb-12">
              <span className="inline-block text-gs-threat text-[11px] font-mono tracking-widest uppercase px-3 py-1 rounded-full border border-gs-threat/20 bg-gs-threat-soft mb-4">
                Threat Intelligence
              </span>
              <h2 className="text-2xl md:text-3xl font-heading font-bold text-gs-text mb-3">
                Attack Types Detected
              </h2>
              <p className="text-sm text-gs-muted">
                Trained on{' '}
                <span className="text-gs-heal font-mono font-medium">575,000+</span>
                {' '}CICIDS2017 network flow records
              </p>
            </motion.div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {ATTACK_TYPES.map((attack, index) => (
                <motion.div
                  key={attack.name}
                  {...fadeUp}
                  transition={{ delay: index * 0.07 }}
                  whileHover={{ y: -3 }}
                  className="gs-panel p-4 text-center cursor-default transition-all duration-200"
                  style={{ borderColor: `${attack.color}20` }}
                >
                  <div className="relative mx-auto mb-3 w-8 h-8 flex items-center justify-center">
                    <div
                      className="absolute w-8 h-8 rounded-full opacity-15"
                      style={{ backgroundColor: attack.color }}
                    />
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: attack.color }}
                    />
                  </div>

                  <h3
                    className="text-[13px] font-heading font-semibold mb-1"
                    style={{ color: attack.color }}
                  >
                    {attack.name}
                  </h3>
                  <p className="text-[10px] text-gs-muted font-mono mb-2 leading-relaxed">
                    {attack.signal}
                  </p>
                  <div
                    className="text-[9px] font-mono truncate px-1.5 py-0.5 rounded border"
                    style={{
                      color: `${attack.color}80`,
                      borderColor: `${attack.color}15`,
                      background: `${attack.color}06`,
                    }}
                    title={attack.dataset}
                  >
                    {attack.dataset}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        <section className="py-16 sm:py-20 px-5 sm:px-6 border-t border-gs-border text-center">
          <motion.div {...fadeUp} className="max-w-xl mx-auto">
            <h2 className="text-2xl font-heading font-bold text-gs-text mb-3">
              Ready to monitor your network?
            </h2>
            <p className="text-gs-muted text-sm mb-7 max-w-sm mx-auto">
              Open the live dashboard to see real-time threat detection, graph visualization, and blockchain forensics.
            </p>
            <Link
              to="/login"
              id="cta-footer-dashboard"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-gs-heal text-white font-heading font-semibold text-sm hover:bg-gs-heal/90 transition-colors duration-200 no-underline w-full sm:w-auto"
            >
              Open Dashboard -&gt;
            </Link>
          </motion.div>
        </section>
      </main>

      <Footer />
    </div>
  )
}
