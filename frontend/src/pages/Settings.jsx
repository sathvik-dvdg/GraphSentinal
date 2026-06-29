// [Windows] GraphSentinel — Susheep
// Settings — tabbed configuration page: Simulation / Detection / Network / Blockchain
import { useState } from 'react'
import { Settings as SettingsIcon, Zap, Shield, Network, Link2 } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'

const TABS = [
  { id: 'simulation',  label: 'Simulation',           icon: <Zap size={14} /> },
  { id: 'detection',   label: 'Detection Thresholds', icon: <Shield size={14} /> },
  { id: 'network',     label: 'Network Config',        icon: <Network size={14} /> },
  { id: 'blockchain',  label: 'Blockchain',            icon: <Link2 size={14} /> },
]

const ATTACK_TYPES = ['DDoS', 'SSHBrute', 'PortScan', 'Botnet']

export default function Settings() {
  const [activeTab, setActiveTab] = useState('simulation')
  const { connectionMode, setConnectionMode, isConnected } = useGraphStore()

  // Simulation
  const isSimulating = connectionMode === 'simulating'
  const [simSpeed, setSimSpeed] = useState('1x')
  const [injectType, setInjectType] = useState('DDoS')
  const [injectTarget, setInjectTarget] = useState('10.0.0.2')

  // Detection
  const [anomalyThreshold, setAnomalyThreshold] = useState(70)
  const [isolateThreshold, setIsolateThreshold] = useState(85)
  const [lateralSensitivity, setLateralSensitivity] = useState('normal')

  // Blockchain
  const [ganacheUrl, setGanacheUrl] = useState('http://127.0.0.1:8545')
  const [contractAddr, setContractAddr] = useState('')
  const [gasLimit, setGasLimit] = useState(200000)

  const toggleSimulation = () => {
    if (isSimulating) {
      setConnectionMode(isConnected ? 'live' : 'mock')
    } else {
      setConnectionMode('simulating')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div>
        <h1 style={{ color: '#E8EDF5', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Settings
        </h1>
        <p style={{ color: '#5A6480', fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
          System configuration · Detection tuning · Network management
        </p>
      </div>

      {/* Tab nav */}
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.06)', gap: 2 }}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              padding: '10px 18px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid #4F6EF7' : '2px solid transparent',
              color: activeTab === tab.id ? '#4F6EF7' : '#5A6480',
              fontSize: 12,
              fontFamily: "'DM Mono', monospace",
              cursor: 'pointer',
              transition: 'all 150ms',
              fontWeight: activeTab === tab.id ? 600 : 400,
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ maxWidth: 640 }}>
        {activeTab === 'simulation' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <Section title="Simulation Mode">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <div>
                  <div style={{ color: '#E8EDF5', fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 500, marginBottom: 3 }}>
                    Enable Simulation
                  </div>
                  <div style={{ color: '#5A6480', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                    {isSimulating ? 'Demo attack sequence is running' : 'Live or mock mode active'}
                  </div>
                </div>
                <Toggle active={isSimulating} onClick={toggleSimulation} />
              </div>
            </Section>

            <Section title="Simulation Speed">
              <div style={{ display: 'flex', gap: 8 }}>
                {['1x', '5x', '10x'].map((s) => (
                  <button
                    key={s}
                    onClick={() => setSimSpeed(s)}
                    style={optionBtnStyle(simSpeed === s, '#E8922A')}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </Section>

            <Section title="Inject Attack">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <Label>Attack Type</Label>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {ATTACK_TYPES.map((t) => (
                      <button key={t} onClick={() => setInjectType(t)} style={optionBtnStyle(injectType === t, '#E03C3C')}>
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label>Target IP</Label>
                  <input
                    value={injectTarget}
                    onChange={(e) => setInjectTarget(e.target.value)}
                    style={inputStyle}
                    placeholder="10.0.0.x"
                  />
                </div>
                <button style={{ ...primaryBtnStyle('#E03C3C'), alignSelf: 'flex-start' }}
                  onClick={() => alert(`Inject ${injectType} → ${injectTarget} (connect to backend)`)}>
                  Inject Attack
                </button>
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'detection' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <Section title="Anomaly Score Threshold">
              <SliderSetting
                label="Alert fires above this score"
                value={anomalyThreshold}
                onChange={setAnomalyThreshold}
                color="#E8922A"
              />
            </Section>

            <Section title="Auto-Isolate Threshold">
              <SliderSetting
                label="Nodes are isolated above this score"
                value={isolateThreshold}
                onChange={setIsolateThreshold}
                color="#E03C3C"
              />
            </Section>

            <Section title="Lateral Movement Sensitivity">
              <div style={{ display: 'flex', gap: 8 }}>
                {['strict', 'normal', 'permissive'].map((s) => (
                  <button
                    key={s}
                    onClick={() => setLateralSensitivity(s)}
                    style={optionBtnStyle(lateralSensitivity === s, '#4F6EF7')}
                  >
                    {s}
                  </button>
                ))}
              </div>
              <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 8 }}>
                {lateralSensitivity === 'strict' ? 'Any cross-level connection triggers alert'
                  : lateralSensitivity === 'normal' ? 'L3→L0 escalations trigger alert'
                  : 'Only confirmed attack patterns trigger alert'}
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'network' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <Section title="Import Org Hierarchy">
              <Label>Upload hierarchy JSON</Label>
              <input
                type="file"
                accept=".json"
                onChange={(e) => alert('JSON import — connect to pyramidConfig loader')}
                style={{ color: '#8A95B0', fontSize: 12, fontFamily: "'DM Mono', monospace" }}
              />
              <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 6 }}>
                Upload a JSON file matching the ORG_HIERARCHY schema to override the default hierarchy.
              </div>
            </Section>

            <Section title="Node Editor">
              <div style={{ color: '#5A6480', fontSize: 12, fontFamily: "'DM Mono', monospace", padding: '20px', textAlign: 'center', border: '1px dashed rgba(255,255,255,0.08)', borderRadius: 8 }}>
                Node editor table (ID / IP / Label / Level / Department)
                <br />
                <span style={{ fontSize: 11, opacity: 0.6 }}>— Connect to hierarchy state to enable add/edit/delete —</span>
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'blockchain' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <Section title="Ganache Connection">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <Label>RPC URL</Label>
                  <input value={ganacheUrl} onChange={(e) => setGanacheUrl(e.target.value)} style={inputStyle} />
                </div>
                <div>
                  <Label>Contract Address</Label>
                  <input value={contractAddr} onChange={(e) => setContractAddr(e.target.value)} style={inputStyle} placeholder="0x..." />
                </div>
                <div>
                  <Label>Gas Limit</Label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <input
                      type="range" min={50000} max={500000} step={10000}
                      value={gasLimit} onChange={(e) => setGasLimit(Number(e.target.value))}
                      style={{ flex: 1, accentColor: '#8B5CF6' }}
                    />
                    <span style={{ color: '#8B5CF6', fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 700, minWidth: 70 }}>
                      {gasLimit.toLocaleString()}
                    </span>
                  </div>
                </div>
                <button style={{ ...primaryBtnStyle('#8B5CF6'), alignSelf: 'flex-start' }}
                  onClick={() => alert('Save blockchain config — connect to backend')}>
                  Save Config
                </button>
              </div>
            </Section>
          </div>
        )}
      </div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="gs-panel" style={{ padding: '16px 18px' }}>
      <div style={{ color: '#8A95B0', fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14 }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function Label({ children }) {
  return (
    <div style={{ color: '#5A6480', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
      {children}
    </div>
  )
}

function Toggle({ active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
        background: active ? '#2ECC8A' : 'rgba(255,255,255,0.1)',
        position: 'relative', transition: 'background 200ms', flexShrink: 0,
      }}
    >
      <div style={{
        width: 18, height: 18, borderRadius: '50%', background: '#fff',
        position: 'absolute', top: 3, left: active ? 23 : 3,
        transition: 'left 200ms', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
      }} />
    </button>
  )
}

function SliderSetting({ label, value, onChange, color }) {
  return (
    <div>
      <Label>{label}</Label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <input
          type="range" min={0} max={100}
          value={value} onChange={(e) => onChange(Number(e.target.value))}
          style={{ flex: 1, accentColor: color }}
        />
        <span style={{ color, fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 700, minWidth: 36 }}>
          {value}
        </span>
      </div>
    </div>
  )
}

const inputStyle = {
  width: '100%', background: '#1E1E1E', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 6, padding: '8px 12px', color: '#E8EDF5',
  fontSize: 12, fontFamily: "'DM Mono', monospace", outline: 'none',
}

function optionBtnStyle(active, color) {
  return {
    padding: '6px 16px', borderRadius: 6, cursor: 'pointer',
    border: `1px solid ${active ? color : 'rgba(255,255,255,0.1)'}`,
    background: active ? `${color}18` : 'transparent',
    color: active ? color : '#5A6480',
    fontSize: 12, fontFamily: "'DM Mono', monospace",
    fontWeight: active ? 600 : 400, transition: 'all 150ms',
    textTransform: 'capitalize',
  }
}

function primaryBtnStyle(color) {
  return {
    padding: '8px 20px', borderRadius: 6, cursor: 'pointer',
    border: `1px solid ${color}40`, background: `${color}15`, color,
    fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 500, transition: 'all 150ms',
  }
}
