// [Windows] GraphSentinel — Susheep
// Settings — tabbed configuration page: Simulation / Detection / Network / Blockchain
import { useState, useEffect } from 'react'
import { Zap, Shield, Network, Link2, Lock, RefreshCw } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import { getSettings, updateThreatThreshold, reloadMlModel } from '../services/api'
import useSessionUser from '../hooks/useSessionUser'
import { simulationBlockedReason } from '../utils/connection'
import { GS } from '../constants/colors'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const ADMIN_REQUIRED = 'An admin is required to change this.'

const TABS = [
  { id: 'simulation',  label: 'Simulation',           icon: <Zap size={14} /> },
  { id: 'detection',   label: 'Detection Thresholds', icon: <Shield size={14} /> },
  { id: 'network',     label: 'Network Config',        icon: <Network size={14} /> },
  { id: 'blockchain',  label: 'Blockchain',            icon: <Link2 size={14} /> },
]

const ATTACK_TYPES = ['DDoS', 'SSHBrute', 'PortScan', 'Botnet']

export default function Settings() {
  const [activeTab, setActiveTab] = useState('simulation')
  const { connectionMode, endSimulation, simulateAttack } = useGraphStore()

  // Simulation
  const isSimulating = connectionMode === 'simulating'
  // Audit B20 — changing the threshold and reloading the model are admin-only on
  // the backend. Shown disabled with the reason, never enabled-and-refused.
  const { role } = useSessionUser()
  const isAdmin = role === 'admin'
  const simulateBlocked = simulationBlockedReason(USE_MOCK, connectionMode, role)
  const [simSpeed, setSimSpeed] = useState('1x')
  const [injectType, setInjectType] = useState('DDoS')
  const [injectTarget, setInjectTarget] = useState('10.0.0.2')
  const [injectVictim, setInjectVictim] = useState('')  // '' = random

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
  const [chainConfig, setChainConfig] = useState({ ganache_url: null, contract_address: null, max_gas: null })
  const [chainConfigLoading, setChainConfigLoading] = useState(true)

  useEffect(() => {
    getSettings()
      .then((res) => {
        setIsolateThreshold(Math.round(res.threat_threshold * 100))
        setSavedThreshold(Math.round(res.threat_threshold * 100))
        setThresholdStatus('idle')
        setChainConfig({ ganache_url: res.ganache_url, contract_address: res.contract_address, max_gas: res.blockchain_max_gas ?? null })
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

  // FE-22 — the switch only ends a running simulation. Turning it on used to
  // set the mode to 'simulating' without sending any attack, which stops the
  // polling and drops socket pushes: the whole dashboard froze until someone
  // switched it off, and it bypassed the gate on the Simulate Attack button.
  // Starting a simulation is that button's job, gate included.
  const toggleSimulation = () => {
    if (isSimulating) endSimulation()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div>
        <h1 style={{ color: GS.text, fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 700, fontSize: 22, marginBottom: 4 }}>
          Settings
        </h1>
        <p style={{ color: GS.textSubtle, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
          System configuration · Detection tuning · Network management
        </p>
      </div>

      {/* Tab nav */}
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(17,20,26,0.08)', gap: 2 }}>
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
              borderBottom: activeTab === tab.id ? `2px solid ${GS.primary}` : '2px solid transparent',
              color: activeTab === tab.id ? GS.primary : GS.textSubtle,
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
                  <div style={{ color: GS.text, fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 500, marginBottom: 3 }}>
                    Enable Simulation
                  </div>
                  <div style={{ color: GS.textSubtle, fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                    {isSimulating ? 'Demo attack sequence is running · switch off to end it' : 'Off · start one with Simulate Attack below'}
                  </div>
                </div>
                <Toggle active={isSimulating} onClick={toggleSimulation} disabled={!isSimulating} />
              </div>
            </Section>

            <Section title="Simulation Intensity">
              <div style={{ display: 'flex', gap: 8 }}>
                {['1x', '5x', '10x'].map((s) => (
                  <button
                    key={s}
                    onClick={() => setSimSpeed(s)}
                    style={optionBtnStyle(simSpeed === s, GS.warn)}
                  >
                    {s}
                  </button>
                ))}
              </div>
              <div style={{ color: GS.textFaint, fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 8 }}>
                Multiplies the synthetic flow volume (packets / bytes) sent by "Inject Attack" below — higher values push scores harder toward the isolation threshold.
              </div>
            </Section>

            <Section title="Simulate Attack">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <Label>Attack Type</Label>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {ATTACK_TYPES.map((t) => (
                      <button key={t} onClick={() => setInjectType(t)} style={optionBtnStyle(injectType === t, GS.danger)}>
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <Label>Attacker IP (source)</Label>
                    <input
                      value={injectTarget}
                      onChange={(e) => setInjectTarget(e.target.value)}
                      style={inputStyle}
                      placeholder="10.0.0.x"
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <Label>Victim IP (blank = random)</Label>
                    <input
                      value={injectVictim}
                      onChange={(e) => setInjectVictim(e.target.value)}
                      style={inputStyle}
                      placeholder="auto"
                    />
                  </div>
                </div>
                <button style={{ ...primaryBtnStyle(GS.danger), alignSelf: 'flex-start', opacity: simulateBlocked ? 0.5 : 1, cursor: simulateBlocked ? 'not-allowed' : 'pointer' }}
                  disabled={isSimulating || Boolean(simulateBlocked)}
                  title={simulateBlocked || undefined}
                  onClick={() => simulateAttack({
                    attackType: injectType,
                    targetIp: injectTarget,
                    victimIp: injectVictim.trim() || undefined,
                    speedMultiplier: parseInt(simSpeed, 10) || 1,
                  })}>
                  {isSimulating ? 'Simulating…' : 'Simulate Attack'}
                </button>
                {simulateBlocked && (
                  <div role="note" style={{ color: GS.textSubtle, fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{simulateBlocked}</div>
                )}
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
                color={GS.danger}
                disabled={thresholdStatus === 'loading' || !isAdmin}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
                <button
                  style={{ ...primaryBtnStyle(GS.danger), opacity: (thresholdStatus === 'loading' || isolateThreshold === savedThreshold) ? 0.5 : 1 }}
                  disabled={!isAdmin || thresholdStatus === 'loading' || thresholdStatus === 'saving' || isolateThreshold === savedThreshold}
                  title={isAdmin ? undefined : ADMIN_REQUIRED}
                  onClick={saveThreshold}
                >
                  {thresholdStatus === 'saving' ? 'Saving…' : 'Save'}
                </button>
                <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: thresholdStatus === 'error' ? GS.danger : thresholdStatus === 'saved' ? GS.success : GS.textFaint }}>
                  {!isAdmin && `${ADMIN_REQUIRED} `}
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
                label="Display only — not wired to the backend"
                value={anomalyThreshold}
                onChange={setAnomalyThreshold}
                color={GS.warn}
                readOnly
              />
              <div style={{ color: GS.textFaint, fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 8 }}>
                The backend doesn't have a separate "flag but don't block" stage — scoring above the single Threat Threshold above both alerts and auto-isolates in one step. This slider is left as a UI-only preview until that two-stage behavior actually exists server-side.
              </div>
            </Section>

            {/* Error.md H8 — POST /api/v1/ml/reload exists but nothing in the
                UI could trigger it; an operator who saw HEURISTIC in the topbar
                badge had to curl the endpoint. Admin-only, so it can 403. */}
            <Section title="GraphSAGE Model">
              <MlReloadControl isAdmin={isAdmin} />
            </Section>

            <Section title="Lateral Movement Sensitivity (not implemented)">
              <div style={{ color: GS.textFaint, fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 8 }}>
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
              <div style={{ color: GS.textMuted, fontSize: 12, fontFamily: "'DM Mono', monospace", lineHeight: 1.6 }}>
                The Org Hierarchy / Pyramid view is derived live from real network topology (<code>graphData.nodes</code>) — every host shown is a host that actually exists on the configured network, with its real IP and live status.
              </div>
              <div style={{ color: GS.textFaint, fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 10 }}>
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
                  {/* FE-25 — was a constant "1,000,000" in this file. The backend
                      estimates gas per call and caps it at BLOCKCHAIN_MAX_GAS. */}
                  <Label>Gas Cap per Transaction</Label>
                  <div style={{ color: GS.chain, fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>
                    {chainConfigLoading ? 'Loading…' : chainConfig.max_gas != null ? chainConfig.max_gas.toLocaleString() : '—'}
                  </div>
                  <div style={{ color: GS.textFaint, fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 2 }}>
                    Estimated per call, never above this cap (<code>BLOCKCHAIN_MAX_GAS</code>).
                  </div>
                </div>
                <div style={{ color: GS.textFaint, fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
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
      <div style={{ color: GS.textMuted, fontSize: 11, fontFamily: "'DM Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14 }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function Label({ children }) {
  return (
    <div style={{ color: GS.textSubtle, fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
      {children}
    </div>
  )
}

function Toggle({ active, onClick, disabled = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      style={{
        width: 44, height: 24, borderRadius: 12, border: 'none',
        cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
        background: active ? GS.success : 'rgba(17,20,26,0.12)',
        position: 'relative', transition: 'background 200ms', flexShrink: 0,
      }}
    >
      <div style={{
        width: 18, height: 18, borderRadius: '50%', background: GS.surface,
        position: 'absolute', top: 3, left: active ? 23 : 3,
        transition: 'left 200ms', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
      }} />
    </button>
  )
}

function SliderSetting({ label, value, onChange, color, disabled = false, readOnly = false }) {
  // Error.md U1 — a display-only slider must look non-interactive: dimmed,
  // not-allowed cursor, a lock icon, and a real `disabled` on the input so
  // clicking/dragging does nothing.
  const inert = disabled || readOnly
  return (
    <div>
      <Label>
        {readOnly && <Lock size={10} style={{ verticalAlign: '-1px', marginRight: 4, opacity: 0.6 }} />}
        {label}
      </Label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, opacity: inert ? 0.4 : 1, cursor: readOnly ? 'not-allowed' : 'default' }}>
        <input
          type="range" min={0} max={100}
          value={value} onChange={(e) => onChange && onChange(Number(e.target.value))}
          disabled={inert}
          style={{ flex: 1, accentColor: color, cursor: readOnly ? 'not-allowed' : 'pointer', pointerEvents: readOnly ? 'none' : 'auto' }}
        />
        <span style={{ color, fontSize: 13, fontFamily: "'DM Mono', monospace", fontWeight: 700, minWidth: 36 }}>
          {value}
        </span>
      </div>
    </div>
  )
}

const inputStyle = {
  width: '100%', background: GS.surfaceRaised, border: '1px solid rgba(17,20,26,0.12)',
  borderRadius: 6, padding: '8px 12px', color: GS.text,
  fontSize: 12, fontFamily: "'DM Mono', monospace", outline: 'none',
}

function optionBtnStyle(active, color) {
  return {
    padding: '6px 16px', borderRadius: 6, cursor: 'pointer',
    border: `1px solid ${active ? color : 'rgba(17,20,26,0.12)'}`,
    background: active ? `${color}18` : 'transparent',
    color: active ? color : GS.textSubtle,
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

function MlReloadControl({ isAdmin }) {
  const mlHealth = useGraphStore((s) => s.mlHealth)
  const setMlHealth = useGraphStore((s) => s.setMlHealth)
  const [state, setState] = useState('idle') // idle | loading | ok | error
  const [msg, setMsg] = useState('')

  const mode = mlHealth?.mode || 'model'
  const degraded = mode !== 'model'

  const run = () => {
    setState('loading')
    setMsg('')
    reloadMlModel()
      .then((res) => {
        setMlHealth({ mode: res.mode, degraded_reason: res.degraded_reason ?? null })
        setState(res.mode === 'model' ? 'ok' : 'error')
        setMsg(res.mode === 'model' ? 'Model reloaded — scoring is live GraphSAGE again' : (res.degraded_reason || 'Still degraded after reload'))
      })
      .catch((err) => {
        setState('error')
        setMsg(err?.response?.status === 403 ? 'Admin privilege required' : 'Reload failed — backend unreachable')
      })
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{
          fontSize: 10, fontFamily: "'DM Mono', monospace", fontWeight: 700, padding: '2px 8px', borderRadius: 4,
          background: degraded ? 'rgba(232,146,42,0.12)' : 'rgba(46,204,138,0.1)',
          color: degraded ? GS.warn : GS.success,
          border: `1px solid ${degraded ? 'rgba(232,146,42,0.3)' : 'rgba(46,204,138,0.25)'}`,
          textTransform: 'uppercase', letterSpacing: '0.06em',
        }}>
          {degraded ? 'Heuristic scoring' : 'GraphSAGE model'}
        </span>
        {mlHealth?.degraded_reason && (
          <span style={{ color: GS.textFaint, fontSize: 11, fontFamily: "'DM Mono', monospace" }}>{mlHealth.degraded_reason}</span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button
          style={{ ...primaryBtnStyle(GS.primary), opacity: state === 'loading' || !isAdmin ? 0.5 : 1, cursor: isAdmin ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', gap: 6 }}
          disabled={state === 'loading' || !isAdmin}
          title={isAdmin ? undefined : ADMIN_REQUIRED}
          onClick={run}
        >
          <RefreshCw size={12} className={state === 'loading' ? 'spin-slow' : undefined} />
          {state === 'loading' ? 'Reloading…' : 'Reload Model'}
        </button>
        {msg && (
          <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: state === 'ok' ? GS.success : state === 'error' ? GS.danger : GS.textFaint }}>
            {msg}
          </span>
        )}
      </div>
      <div style={{ color: GS.textFaint, fontSize: 11, fontFamily: "'DM Mono', monospace", marginTop: 8 }}>
        Reloads GraphSAGE weights from disk and clears degraded mode. {isAdmin ? 'Admin only.' : ADMIN_REQUIRED}
      </div>
    </div>
  )
}
