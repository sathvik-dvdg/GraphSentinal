// [Windows] GraphSentinel — Susheep
// Settings — tabbed configuration page: Simulation / Detection / Network / Blockchain
import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Zap, Shield, Network, Link2 } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import { getSettings, updateThreatThreshold } from '../services/api'

const TABS = [
  { id: 'simulation',  label: 'Simulation',           icon: <Zap size={14} /> },
  { id: 'detection',   label: 'Detection Thresholds', icon: <Shield size={14} /> },
  { id: 'network',     label: 'Network Config',        icon: <Network size={14} /> },
  { id: 'blockchain',  label: 'Blockchain',            icon: <Link2 size={14} /> },
]

const ATTACK_TYPES = ['DDoS', 'SSHBrute', 'PortScan', 'Botnet']

export default function Settings() {
  const [activeTab, setActiveTab] = useState('simulation')
  const { connectionMode, setConnectionMode, isConnected, simulateAttack } = useGraphStore()

  // Simulation
  const isSimulating = connectionMode === 'simulating'
  const [simSpeed, setSimSpeed] = useState('1x')
  const [injectType, setInjectType] = useState('DDoS')
  const [injectTarget, setInjectTarget] = useState('10.0.0.2')

  // Detection
  const [anomalyThreshold, setAnomalyThreshold] = useState(70)
  // Error.md #19 — this is the one control with a real backend equivalent
  // (settings.threat_threshold). Starts null until the real value loads so
  // the slider never shows a fabricated default that might not match what
  // the backend is actually running.
  const [isolateThreshold, setIsolateThreshold] = useState(null)
  const [savedThreshold, setSavedThreshold] = useState(null)
  const [thresholdStatus, setThresholdStatus] = useState('loading') // loading | idle | saving | saved | error
  const [alertThreshold, setAlertThreshold] = useState(85)

  // Blockchain — real values, read-only (see note in the Blockchain tab
  // below for why these aren't live-editable)
  const [chainConfig, setChainConfig] = useState({ ganache_url: null, contract_address: null })
  const [chainConfigLoading, setChainConfigLoading] = useState(true)

  useEffect(() => {
    getSettings()
      .then((res) => {
        setIsolateThreshold(Math.round(res.threat_threshold * 100))
        setSavedThreshold(Math.round(res.threat_threshold * 100))
        setThresholdStatus('idle')
        setChainConfig({ ganache_url: res.ganache_url, contract_address: res.contract_address })
      })
      .catch(() => setThresholdStatus('error'))
      .finally(() => setChainConfigLoading(false))
  }, [])

  const saveThreshold = () => {
    setThresholdStatus('saving')
    updateThreatThreshold(isolateThreshold / 100)
      .then((res) => {
        setSavedThreshold(Math.round(res.threat_threshold * 100))
        setThresholdStatus('saved')
        setTimeout(() => setThresholdStatus('idle'), 2000)
      })
      .catch(() => setThresholdStatus('error'))
  }

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
                  disabled={isSimulating}
                  onClick={() => simulateAttack({ attackType: injectType, targetIp: injectTarget })}>
                  {isSimulating ? 'Injecting…' : 'Inject Attack'}
                </button>
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'detection' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <Section title="Threat Threshold">
              {/* Error.md #19: the backend has a single threat_threshold that
                  gates both alerting and auto-block — there is no separate
                  detect-only vs. isolate-only stage. This is the real,
                  live-editable control; the old "Anomaly Score Threshold"
                  slider below is informational only, see its own note. */}
              <SliderSetting
                label="Nodes are alerted AND auto-isolated above this score (live backend value)"
                value={isolateThreshold ?? 0}
                onChange={setIsolateThreshold}
                color="#E03C3C"
                disabled={thresholdStatus === 'loading'}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
                <button
                  style={{ ...primaryBtnStyle('#E03C3C'), opacity: (thresholdStatus === 'loading' || isolateThreshold === savedThreshold) ? 0.5 : 1 }}
                  disabled={thresholdStatus === 'loading' || thresholdStatus === 'saving' || isolateThreshold === savedThreshold}
                  onClick={saveThreshold}
                >
                  {thresholdStatus === 'saving' ? 'Saving…' : 'Save'}
                </button>
                <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: thresholdStatus === 'error' ? '#E03C3C' : thresholdStatus === 'saved' ? '#2ECC8A' : '#3D4560' }}>
                  {thresholdStatus === 'loading' && 'Loading current value from backend…'}
                  {thresholdStatus === 'error' && 'Failed to reach the backend'}
                  {thresholdStatus === 'saved' && `Saved — live threshold is now ${(savedThreshold / 100).toFixed(2)}`}
                  {thresholdStatus === 'idle' && isolateThreshold !== savedThreshold && 'Unsaved change'}
                  {thresholdStatus === 'idle' && isolateThreshold === savedThreshold && `Current live value: ${(savedThreshold / 100).toFixed(2)} (resets to .env default on backend restart)`}
                </span>
              </div>
            </Section>

            <Section title="Anomaly Score Threshold (display only)">
              <SliderSetting
                label="Not wired to the backend — see note below"
                value={anomalyThreshold}
                onChange={setAnomalyThreshold}
                color="#E8922A"
              />
              <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 8 }}>
                The backend doesn't have a separate "flag but don't block" stage — scoring above the single Threat Threshold above both alerts and auto-isolates in one step. This slider is left as a UI-only preview until that two-stage behavior actually exists server-side.
              </div>
            </Section>

            <Section title="Lateral Movement Sensitivity (not implemented)">
              <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 8 }}>
                The backend has no lateral-movement detection logic at all yet (no L3→L0 escalation tracking) — this control has nothing to connect to.
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'network' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Error.md #2 already replaced the hierarchy view with one
                derived live from real graph data instead of an editable
                admin-entered org chart — so "import a JSON to override it"
                and a manual node editor are both stale ideas that would
                reintroduce exactly the fake-data problem #2 fixed. Removed
                the controls rather than wiring up something that would
                undermine that fix; explaining why instead. */}
            <Section title="Org Hierarchy Source">
              <div style={{ color: '#8A95B0', fontSize: 12, fontFamily: "'DM Mono', monospace", lineHeight: 1.6 }}>
                The Org Hierarchy / Pyramid view is derived live from real network topology (<code>graphData.nodes</code>) — every host shown is a host that actually exists on the configured network, with its real IP and live status.
              </div>
              <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 10 }}>
                A JSON import / manual node editor to override it was removed rather than wired up — either would reintroduce admin-entered data that could silently diverge from what's actually on the network, which is the exact problem the live-derived hierarchy was built to fix.
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'blockchain' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Error.md #19: these used to be editable text fields that did
                nothing on save. They're real values now (fetched from
                /api/v1/settings), but read-only rather than fake-editable —
                the blockchain adapter connects to Ganache once at process
                startup and is a singleton; changing which chain/contract
                security incidents get logged to, live, via a text field, is
                a genuinely risky action, not just a missing wire-up. */}
            <Section title="Ganache Connection (read-only — live backend values)">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <Label>RPC URL</Label>
                  <input value={chainConfigLoading ? 'Loading…' : (chainConfig.ganache_url || '—')} readOnly style={{ ...inputStyle, opacity: 0.7, cursor: 'default' }} />
                </div>
                <div>
                  <Label>Contract Address</Label>
                  <input value={chainConfigLoading ? 'Loading…' : (chainConfig.contract_address || 'Not deployed / not connected')} readOnly style={{ ...inputStyle, opacity: 0.7, cursor: 'default' }} />
                </div>
                <div>
                  <Label>Gas Limit (fixed)</Label>
                  <div style={{ color: '#8B5CF6', fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
                    1,000,000
                  </div>
                </div>
                <div style={{ color: '#3D4560', fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                  To change these, edit <code>GANACHE_URL</code> / <code>CONTRACT_ADDRESS</code> in the backend's env config and restart — reconnecting live from the UI isn't supported (it would mean silently switching which chain security incidents get written to while the app keeps running).
                </div>
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

function SliderSetting({ label, value, onChange, color, disabled = false }) {
  return (
    <div>
      <Label>{label}</Label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, opacity: disabled ? 0.5 : 1 }}>
        <input
          type="range" min={0} max={100}
          value={value} onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
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
