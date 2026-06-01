# 🖥️ SUSHEEP — FRONTEND IMPLEMENTATION PLAN
## GraphSentinel | Role: Frontend Engineer
### AI IDE: Claude Code / AntGravity / Codex | Platform: Windows Native

---

## PASTE THIS EXACT BLOCK WHEN STARTING YOUR AI IDE SESSION

```
You are the frontend implementation assistant for GraphSentinel —
a Self-Healing Cyber Defense System with a 3D cyber threat dashboard.

YOUR ROLE: You assist Susheep who is building the React dashboard
with real-time 3D network visualization and blockchain forensics display.

FROZEN CONSTRAINTS — NEVER VIOLATE:
- React: 18.x | Build tool: Vite 5.x (NOT Create React App)
- Package manager: npm ONLY
- 3D visualization: react-force-graph-3d (primary) + @react-three/fiber (optional)
- 2D fallback: cytoscape / react-cytoscapejs (toggle button)
- Real-time: socket.io-client@4
- Charts: recharts@2
- Styling: Tailwind CSS 3.x + framer-motion 11.x
- State: Zustand (lightweight — no Redux)
- API client: axios@1.7
- OS: Windows 11 (Vite dev server on port 5173)

MOCK DATA STRATEGY:
  All mock data lives in src/services/mockData.js ONLY.
  Every component uses props — never imports mockData directly.
  Every mock data structure has a // TODO: REPLACE comment.
  When backend is ready, only api.js + useWebSocket.js change.
  Components never need modification when switching to real data.

BACKEND API CONTRACTS (Frozen — design components around these):
  GET  /api/v1/graph         → GraphResponse (nodes[], links[])
  GET  /api/v1/alerts        → AlertsResponse
  GET  /api/v1/blocked       → BlockedIPsResponse
  GET  /api/v1/forensics     → ForensicsResponse (incidents + blockchain_records)
  POST /api/v1/block         → BlockResult
  WebSocket: 'graph_update'  → every 5s → GraphResponse
  WebSocket: 'alert'         → on new incident
  WebSocket: 'healing_triggered' → on node isolation

NODE STATUS COLORS (never change):
  normal     → #00ff88 (neon green)
  suspicious → #ffaa00 (amber)
  malicious  → #ff4444 (red, pulsing)
  blocked    → #0066ff (blue, with cage wireframe)

Dashboard theme: bg #0a0e1a | cards #111827 | accent #00ff88

When I ask to scaffold, generate full component code.
Always add OS comment: // [Windows] at top of every React file.
Never use localStorage or sessionStorage — use React state only.
```

---

## WEEK-BY-WEEK TASK BREAKDOWN

### WEEK 1 — Project Setup + Dashboard Shell [Windows]

```powershell
# [Windows PowerShell]
# STEP 1: Verify Node.js
node --version   # Need v18.x or v20.x LTS
npm --version    # Need 9.x or 10.x

# STEP 2: Navigate to frontend folder
cd C:\Projects\graphsentinel\frontend

# STEP 3: Scaffold Vite React project
npm create vite@latest . -- --template react
# Answer: y (proceed), React, JavaScript

# STEP 4: Install all dependencies at once
npm install

# Core visualization
npm install react-force-graph-3d three@0.167.0
npm install @react-three/fiber@8 @react-three/drei@9
npm install cytoscape@3.28.0 react-cytoscapejs

# Real-time + API
npm install socket.io-client@4 axios@1.7

# UI
npm install recharts@2 lucide-react tailwindcss framer-motion
npm install zustand
npm install -D autoprefixer postcss

# STEP 5: Init Tailwind
npx tailwindcss init -p

# STEP 6: Test it runs
npm run dev
# Should open: http://localhost:5173
# You should see default Vite + React page

echo "Week 1 setup complete ✓"
```

**Configure Tailwind CSS:**

```javascript
// tailwind.config.js  [Windows]
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        'gs-bg':      '#0a0e1a',
        'gs-card':    '#111827',
        'gs-accent':  '#00ff88',
        'gs-alert':   '#ff4444',
        'gs-warn':    '#ffaa00',
        'gs-info':    '#0099ff',
        'gs-chain':   '#9945ff',
        'gs-border':  '#1f2937',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Courier New', 'monospace'],
      }
    },
  },
  plugins: [],
}
```

```css
/* src/styles/globals.css  [Windows] */
@tailwind base;
@tailwind components;
@tailwind utilities;

@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background-color: #0a0e1a;
  color: #e2e8f0;
  font-family: 'JetBrains Mono', monospace;
  overflow: hidden;
}

/* Glowing pulse for malicious nodes label */
@keyframes pulse-red {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
.malicious-pulse { animation: pulse-red 1.2s ease-in-out infinite; }

/* Scrollbar styling for dark theme */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #111827; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 2px; }
```

**Week 1 Checkpoint:** `npm run dev` renders dark page at localhost:5173.

---

### WEEK 2 — Static UI With All Mock Data Wired

**Dashboard Layout:**

```jsx
// src/App.jsx  [Windows]
import { useState, useEffect } from 'react'
import NetworkGraph3D from './components/NetworkGraph3D/NetworkGraph3D'
import NetworkGraph2D from './components/NetworkGraph2D/NetworkGraph2D'
import AlertPanel from './components/AlertPanel/AlertPanel'
import BlockchainPanel from './components/BlockchainLedger/BlockchainPanel'
import SelfHealStatus from './components/SelfHealingStatus/SelfHealStatus'
import ThreatTimeline from './components/ThreatTimeline/ThreatTimeline'
import StatsBar from './components/StatsBar/StatsBar'
import {
  MOCK_GRAPH_DATA, MOCK_ALERTS, MOCK_BLOCKED,
  MOCK_BLOCKCHAIN_TXS, MOCK_STATS, MOCK_HEALING_EVENTS,
  MOCK_TIMELINE
} from './services/mockData'
import './styles/globals.css'

export default function App() {
  // TODO: Replace all useState initializations with real API data
  // See useGraphData.js and useWebSocket.js hooks when backend is ready
  const [graphData,      setGraphData]     = useState(MOCK_GRAPH_DATA)
  const [alerts,         setAlerts]        = useState(MOCK_ALERTS)
  const [blocked,        setBlocked]       = useState(MOCK_BLOCKED)
  const [chainTxs,       setChainTxs]      = useState(MOCK_BLOCKCHAIN_TXS)
  const [stats,          setStats]         = useState(MOCK_STATS)
  const [healingEvents,  setHealingEvents] = useState(MOCK_HEALING_EVENTS)
  const [timeline,       setTimeline]      = useState(MOCK_TIMELINE)
  const [use3D,          setUse3D]         = useState(true)
  const [healingNodeId,  setHealingNodeId] = useState(null)
  const [isMockMode,     setIsMockMode]    = useState(true)
  // TODO: isMockMode → false when VITE_USE_MOCK=false and backend is live

  return (
    <div className="h-screen w-screen bg-gs-bg flex flex-col overflow-hidden">
      {/* ── Top Status Bar ─────────────────────────────────────── */}
      <StatsBar stats={stats} isMockMode={isMockMode} />

      {/* ── Main Content Grid ──────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden gap-1 p-1">
        {/* Left: 3D/2D Graph */}
        <div className="flex-1 relative rounded-lg overflow-hidden border border-gs-border">
          {/* Toggle button */}
          <button
            onClick={() => setUse3D(v => !v)}
            className="absolute top-3 right-3 z-10 bg-gs-card border border-gs-border
                       text-xs text-gray-400 px-3 py-1 rounded hover:border-gs-accent
                       hover:text-gs-accent transition-colors font-mono"
          >
            {use3D ? '[ 2D MODE ]' : '[ 3D MODE ]'}
          </button>

          {use3D
            ? <NetworkGraph3D
                graphData={graphData}
                healingNodeId={healingNodeId}
                onNodeClick={(node) => console.log('Selected:', node.id)}
              />
            : <NetworkGraph2D
                graphData={graphData}
                healingNodeId={healingNodeId}
              />
          }
        </div>

        {/* Right panel column */}
        <div className="w-80 flex flex-col gap-1 overflow-hidden">
          {/* Alert feed */}
          <div className="flex-1 overflow-auto">
            <AlertPanel alerts={alerts} />
          </div>

          {/* Blockchain ledger */}
          <div className="flex-1 overflow-auto">
            <BlockchainPanel transactions={chainTxs} />
          </div>

          {/* Self-healing status */}
          <div className="overflow-auto max-h-48">
            <SelfHealStatus events={healingEvents} />
          </div>
        </div>
      </div>

      {/* ── Bottom Timeline ─────────────────────────────────────── */}
      <div className="h-28 border-t border-gs-border px-2 pb-1">
        <ThreatTimeline data={timeline} />
      </div>
    </div>
  )
}
```

**Week 2 Checkpoint:** Full dashboard visible with all panels, dark theme, mock data in every component.

---

### WEEK 3 — 3D Network Graph Component (Core Feature)

```jsx
// src/components/NetworkGraph3D/NetworkGraph3D.jsx  [Windows]
import React, { useRef, useCallback, useEffect, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'

// ─── Node Status → Color mapping ──────────────────────────────────
const STATUS_COLOR = {
  normal:     '#00ff88',
  suspicious: '#ffaa00',
  malicious:  '#ff4444',
  blocked:    '#0066ff',
}

const LINK_COLOR = {
  DDoS:     '#ff4444',
  SSHBrute: '#ff8800',
  PortScan: '#ffff00',
  Botnet:   '#aa44ff',
  DoSHulk:  '#ff2266',
  null:     '#1e3a5f',
}

export default function NetworkGraph3D({
  graphData,        // { nodes: [...], links: [...] }
  healingNodeId,    // IP of node currently being isolated (for animation)
  onNodeClick,
}) {
  const fgRef = useRef()
  const [animatedNodeId, setAnimatedNodeId] = useState(null)

  // ── Healing animation trigger ────────────────────────────────────
  useEffect(() => {
    if (healingNodeId) {
      setAnimatedNodeId(healingNodeId)
      setTimeout(() => setAnimatedNodeId(null), 3000)
    }
  }, [healingNodeId])

  // ── Auto-rotate camera slowly ────────────────────────────────────
  useEffect(() => {
    let angle = 0
    const timer = setInterval(() => {
      if (fgRef.current) {
        angle += 0.003
        fgRef.current.cameraPosition({
          x: 200 * Math.sin(angle),
          z: 200 * Math.cos(angle),
        })
      }
    }, 50)
    return () => clearInterval(timer)
  }, [])

  // ── Custom 3D node mesh ──────────────────────────────────────────
  const nodeThreeObject = useCallback((node) => {
    const group = new THREE.Group()
    const isHealing   = node.id === animatedNodeId
    const isMalicious = node.status === 'malicious'
    const isBlocked   = node.status === 'blocked'
    const isSuspicious= node.status === 'suspicious'

    // Main sphere — size by threat level
    const radius = isMalicious ? 7 : isBlocked ? 6 : isSuspicious ? 5 : 4
    const geo  = new THREE.SphereGeometry(radius, 20, 20)
    const mat  = new THREE.MeshPhongMaterial({
      color:             new THREE.Color(STATUS_COLOR[node.status] || '#ffffff'),
      emissive:          new THREE.Color(isMalicious ? '#ff1111' : '#000000'),
      emissiveIntensity: isMalicious ? 0.7 : 0,
      transparent:       isBlocked,
      opacity:           isBlocked ? 0.8 : 1,
      shininess:         100,
    })
    const sphere = new THREE.Mesh(geo, mat)
    group.add(sphere)

    // Outer ring for suspicious nodes
    if (isSuspicious) {
      const ringGeo = new THREE.TorusGeometry(8, 0.5, 8, 32)
      const ringMat = new THREE.MeshBasicMaterial({
        color: '#ffaa00', transparent: true, opacity: 0.6
      })
      const ring = new THREE.Mesh(ringGeo, ringMat)
      group.add(ring)
    }

    // Wireframe cage for blocked/isolated nodes
    if (isBlocked) {
      const cageGeo = new THREE.WireframeGeometry(new THREE.SphereGeometry(12, 8, 8))
      const cageMat = new THREE.LineBasicMaterial({
        color: '#0066ff', transparent: true, opacity: 0.5
      })
      group.add(new THREE.LineSegments(cageGeo, cageMat))
    }

    // Healing pulse: expanding sphere animation effect
    if (isHealing) {
      const pulseGeo = new THREE.SphereGeometry(15, 16, 16)
      const pulseMat = new THREE.MeshBasicMaterial({
        color: '#0066ff', transparent: true, opacity: 0.3, wireframe: true
      })
      group.add(new THREE.Mesh(pulseGeo, pulseMat))
    }

    // IP label as sprite
    const canvas  = document.createElement('canvas')
    canvas.width  = 256
    canvas.height = 48
    const ctx     = canvas.getContext('2d')
    ctx.fillStyle = '#ffffff'
    ctx.font      = '20px monospace'
    ctx.fillText(node.label || node.id, 8, 32)
    const tex     = new THREE.CanvasTexture(canvas)
    const spr     = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: tex, transparent: true })
    )
    spr.scale.set(28, 7, 1)
    spr.position.set(0, radius + 10, 0)
    group.add(spr)

    // Threat score badge for malicious/suspicious
    if (node.threat_score >= 0.50) {
      const badgeCanvas  = document.createElement('canvas')
      badgeCanvas.width  = 128
      badgeCanvas.height = 32
      const bctx         = badgeCanvas.getContext('2d')
      bctx.fillStyle     = node.threat_score >= 0.75 ? '#ff4444' : '#ffaa00'
      bctx.fillRect(0, 0, 128, 32)
      bctx.fillStyle     = '#ffffff'
      bctx.font          = 'bold 20px monospace'
      bctx.fillText(`${(node.threat_score * 100).toFixed(0)}%`, 10, 24)
      const badgeTex = new THREE.CanvasTexture(badgeCanvas)
      const badge    = new THREE.Sprite(new THREE.SpriteMaterial({ map: badgeTex }))
      badge.scale.set(18, 5, 1)
      badge.position.set(0, -(radius + 8), 0)
      group.add(badge)
    }

    return group
  }, [animatedNodeId])

  // ── Link color by threat ─────────────────────────────────────────
  const getLinkColor  = useCallback(link => LINK_COLOR[link.attack_type] || LINK_COLOR.null, [])
  const getLinkWidth  = useCallback(link => link.value > 0.75 ? 3 : link.value > 0.5 ? 2 : 1, [])
  const getParticles  = useCallback(link => link.value > 0.75 ? 8 : link.value > 0.5 ? 4 : 1, [])
  const getParticleW  = useCallback(link => link.value > 0.75 ? 3 : 2, [])

  return (
    <div className="w-full h-full bg-gs-bg">
      <ForceGraph3D
        ref={fgRef}
        graphData={graphData}
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        linkColor={getLinkColor}
        linkWidth={getLinkWidth}
        linkDirectionalParticles={getParticles}
        linkDirectionalParticleWidth={getParticleW}
        linkDirectionalParticleSpeed={0.007}
        linkDirectionalParticleColor={getLinkColor}
        backgroundColor="#0a0e1a"
        enableNodeDrag={true}
        enableNavigationControls={true}
        showNavInfo={false}
        onNodeClick={(node) => {
          onNodeClick && onNodeClick(node)
          // Focus camera on clicked node
          const d = 80
          const { x = 0, y = 0, z = 0 } = node
          fgRef.current.cameraPosition(
            { x: x + d, y: y + d, z: z + d },
            { x, y, z },
            1000
          )
        }}
        nodeLabel={node =>
          `<div style="background:#1a2035;border:1px solid #334466;padding:4px 8px;
                       font-family:monospace;font-size:11px;color:#e2e8f0;border-radius:4px">
            <b>${node.label}</b> (${node.id})<br/>
            Status: <span style="color:${STATUS_COLOR[node.status]}">${node.status.toUpperCase()}</span><br/>
            Threat: ${(node.threat_score * 100).toFixed(1)}% |
            Conns: ${node.connections}
           </div>`
        }
      />
    </div>
  )
}
```

---

### WEEK 4 — All Right Panel Components

```jsx
// src/components/StatsBar/StatsBar.jsx  [Windows]
import { motion } from 'framer-motion'

export default function StatsBar({ stats, isMockMode }) {
  // TODO: stats → from GET /api/v1/stats (Sairaj needs to add this endpoint)
  // Or derive from graphData: count nodes by status

  const healthColor = stats.system_health >= 80 ? '#00ff88' :
                      stats.system_health >= 50 ? '#ffaa00' : '#ff4444'

  return (
    <div className="flex items-center justify-between px-4 py-2
                    bg-gs-card border-b border-gs-border text-xs font-mono">

      {/* Logo */}
      <div className="flex items-center gap-3">
        <span className="text-gs-accent font-bold text-sm">🛡️ GRAPHSENTINEL</span>
        {isMockMode && (
          <span className="bg-yellow-500/20 text-yellow-400 border border-yellow-500/30
                           px-2 py-0.5 rounded text-xs">
            SIMULATION MODE
          </span>
        )}
        {/* TODO: Remove SIMULATION MODE badge when backend connects */}
      </div>

      {/* Stats */}
      <div className="flex items-center gap-6">
        <Stat label="NODES"    value={stats.total_nodes}       color="#e2e8f0" />
        <Stat label="MALICIOUS" value={stats.malicious_nodes}  color="#ff4444" />
        <Stat label="BLOCKED"  value={stats.blocked_nodes}     color="#0066ff" />
        <Stat label="THREATS"  value={stats.total_threats_today} color="#ff4444" />
        <Stat label="CHAIN TXs" value={stats.blockchain_tx_count} color="#9945ff" />
      </div>

      {/* System health */}
      <div className="flex items-center gap-2">
        <span className="text-gray-500">SYSTEM HEALTH</span>
        <motion.span
          style={{ color: healthColor }}
          animate={{ opacity: [1, 0.5, 1] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="font-bold"
        >
          {stats.system_health}%
        </motion.span>
        <span className="text-gray-600 text-xs">
          {new Date().toLocaleTimeString()}
        </span>
      </div>
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div className="flex flex-col items-center">
      <span className="text-gray-600 text-xs">{label}</span>
      <span className="font-bold" style={{ color }}>{value}</span>
    </div>
  )
}
```

```jsx
// src/components/AlertPanel/AlertPanel.jsx  [Windows]
import { motion, AnimatePresence } from 'framer-motion'

const SEVERITY_STYLE = {
  critical: { border: 'border-red-500/40',   badge: 'bg-red-500/20 text-red-400',   dot: '#ff4444' },
  warning:  { border: 'border-yellow-500/30', badge: 'bg-yellow-500/20 text-yellow-400', dot: '#ffaa00' },
  info:     { border: 'border-blue-500/20',  badge: 'bg-blue-500/20 text-blue-400',  dot: '#0099ff' },
}

export default function AlertPanel({ alerts }) {
  // TODO: Replace alerts prop with:
  //   const { data } = useSWR('/api/v1/alerts', fetcher)
  //   Or from useAlerts() hook once backend is live

  return (
    <div className="bg-gs-card rounded-lg p-3 border border-gs-border h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-red-400 font-mono text-xs font-bold">
          🚨 THREAT FEED
        </h3>
        <span className="text-gray-600 text-xs">{alerts.length} events</span>
      </div>

      <div className="flex-1 overflow-auto space-y-1.5">
        <AnimatePresence initial={false}>
          {alerts.map((alert, i) => {
            const style = SEVERITY_STYLE[alert.severity] || SEVERITY_STYLE.info
            return (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: 20, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3, delay: i * 0.05 }}
                className={`p-2 rounded border ${style.border} bg-gs-bg/50`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {/* Live dot */}
                  <motion.div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: style.dot }}
                    animate={alert.severity === 'critical'
                      ? { scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }
                      : {}}
                    transition={{ duration: 1.2, repeat: Infinity }}
                  />
                  <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${style.badge}`}>
                    {alert.attack_type}
                  </span>
                  <span className="text-gray-400 text-xs ml-auto">
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                <div className="text-gray-300 text-xs font-mono">
                  {alert.source_ip}
                </div>

                {/* Threat bar */}
                <div className="mt-1 flex items-center gap-2">
                  <span className="text-gray-600 text-xs">Threat:</span>
                  <div className="flex-1 bg-gray-800 rounded-full h-1">
                    <motion.div
                      className="h-1 rounded-full"
                      style={{ backgroundColor: style.dot }}
                      initial={{ width: 0 }}
                      animate={{ width: `${alert.threat_score * 100}%` }}
                      transition={{ duration: 0.8, delay: i * 0.1 }}
                    />
                  </div>
                  <span className="text-xs" style={{ color: style.dot }}>
                    {(alert.threat_score * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Blockchain hash */}
                {alert.blockchain_tx && (
                  <div className="mt-1 text-purple-400 text-xs font-mono">
                    ⛓️ {alert.blockchain_tx.slice(0,12)}...
                    <span className="text-green-400 ml-1">✓ on-chain</span>
                  </div>
                )}

                {alert.is_blocked && (
                  <div className="mt-1 text-blue-400 text-xs">
                    🔒 Node isolated
                  </div>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>

        {alerts.length === 0 && (
          <div className="text-gray-700 text-xs text-center py-4 font-mono">
            No threats detected.
          </div>
        )}
      </div>
    </div>
  )
}
```

```jsx
// src/components/ThreatTimeline/ThreatTimeline.jsx  [Windows]
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend
} from 'recharts'

export default function ThreatTimeline({ data }) {
  // TODO: Replace data prop with real timeline:
  //   GET /api/v1/timeline?last=60min (Sairaj needs to add this endpoint)
  //   Or aggregate from alert events received via WebSocket

  return (
    <div className="h-full flex flex-col">
      <h3 className="text-gray-400 font-mono text-xs mb-1">📈 THREAT TIMELINE</h3>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="threats" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ff4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ff4444" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="blocked" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#0066ff" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#0066ff" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 10 }} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              background: '#111827', border: '1px solid #374151',
              borderRadius: '6px', fontFamily: 'monospace', fontSize: '11px'
            }}
          />
          <Area type="monotone" dataKey="threats" stroke="#ff4444"
                fill="url(#threats)" strokeWidth={2} dot={false}
                name="Threats" />
          <Area type="monotone" dataKey="blocked" stroke="#0066ff"
                fill="url(#blocked)" strokeWidth={2} dot={false}
                name="Blocked" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
```

**Week 4 Checkpoint:** All components visible, themed, wired to mock data.

---

### WEEK 5 — Connect to Real Backend

```javascript
// src/services/api.js  [Windows]
// ─────────────────────────────────────────────────────────────
// Axios API client — calls Sairaj's FastAPI backend.
// Vite proxy in vite.config.js redirects /api → http://localhost:8000
// ─────────────────────────────────────────────────────────────
import axios from 'axios'

const api = axios.create({
  baseURL: '/',   // Vite proxy handles /api → backend
  timeout: 5000,
})

// Request interceptor: log all calls
api.interceptors.request.use(config => {
  console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`)
  return config
})

// Response interceptor: handle errors gracefully
api.interceptors.response.use(
  r => r.data,
  err => {
    console.error(`[API] Error: ${err.response?.status} ${err.config?.url}`)
    throw err
  }
)

// ── API Functions ─────────────────────────────────────────────

// GET /api/v1/graph — initial graph load
export const getGraph = () => api.get('/api/v1/graph')

// GET /api/v1/alerts?limit=50
export const getAlerts = (limit = 50) =>
  api.get('/api/v1/alerts', { params: { limit } })

// GET /api/v1/blocked
export const getBlocked = () => api.get('/api/v1/blocked')

// GET /api/v1/forensics
export const getForensics = () => api.get('/api/v1/forensics')

// POST /api/v1/block
export const blockIP = (ip, reason = 'MANUAL_OVERRIDE') =>
  api.post('/api/v1/block', { ip, reason })

export default api
```

```javascript
// src/hooks/useGraphData.js  [Windows]
import { useState, useEffect, useCallback } from 'react'
import { getGraph, getAlerts, getBlocked, getForensics } from '../services/api'
import {
  MOCK_GRAPH_DATA, MOCK_ALERTS, MOCK_BLOCKED,
  MOCK_BLOCKCHAIN_TXS, MOCK_STATS
} from '../services/mockData'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export function useGraphData() {
  const [graphData,   setGraphData]   = useState(MOCK_GRAPH_DATA)
  const [alerts,      setAlerts]      = useState(MOCK_ALERTS)
  const [blocked,     setBlocked]     = useState(MOCK_BLOCKED)
  const [chainTxs,    setChainTxs]    = useState(MOCK_BLOCKCHAIN_TXS)
  const [stats,       setStats]       = useState(MOCK_STATS)
  const [isMockMode,  setIsMockMode]  = useState(true)
  const [isLoading,   setIsLoading]   = useState(false)
  const [error,       setError]       = useState(null)

  const fetchAll = useCallback(async () => {
    if (USE_MOCK) return  // Stay on mock data

    setIsLoading(true)
    try {
      // TODO: These calls go live once Sairaj's backend is running
      const [graphRes, alertsRes, blockedRes, forensicsRes] = await Promise.allSettled([
        getGraph(),
        getAlerts(),
        getBlocked(),
        getForensics(),
      ])

      if (graphRes.status === 'fulfilled') {
        setGraphData(graphRes.value)
        setIsMockMode(false)
      }
      if (alertsRes.status === 'fulfilled')
        setAlerts(alertsRes.value.alerts)
      if (blockedRes.status === 'fulfilled')
        setBlocked(blockedRes.value.blocked_ips)
      if (forensicsRes.status === 'fulfilled') {
        setChainTxs(forensicsRes.value.blockchain_records)
        setStats(prev => ({
          ...prev,
          blockchain_tx_count: forensicsRes.value.total_on_chain
        }))
      }
    } catch (e) {
      setError(e.message)
      console.warn('[useGraphData] Backend unavailable — keeping mock data')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    // Poll every 10s as REST fallback (WebSocket is primary)
    const interval = setInterval(fetchAll, 10000)
    return () => clearInterval(interval)
  }, [fetchAll])

  return {
    graphData, setGraphData,
    alerts, setAlerts,
    blocked, setBlocked,
    chainTxs, setChainTxs,
    stats, setStats,
    isMockMode, isLoading, error,
    refresh: fetchAll,
  }
}
```

```javascript
// src/hooks/useWebSocket.js  [Windows]
import { useEffect, useRef } from 'react'
import { io } from 'socket.io-client'

const WS_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

export function useWebSocket({ onGraphUpdate, onAlert, onHealingTriggered }) {
  const socketRef = useRef(null)
  const connected = useRef(false)

  useEffect(() => {
    // TODO: This ALREADY connects to real backend when it's available.
    // During Week 1-4 development, backend won't be up, so socket
    // will fail silently and we fall back to mock data.
    const socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 3,
      reconnectionDelay: 2000,
      timeout: 5000,
    })

    socket.on('connect', () => {
      connected.current = true
      console.log('[WS] Connected to GraphSentinel backend ✓')
    })

    // Fires every 5 seconds with full graph state
    socket.on('graph_update', data => {
      if (onGraphUpdate) onGraphUpdate(data)
    })

    // Fires when threat_score >= 0.75
    socket.on('alert', data => {
      if (onAlert) onAlert(data)
    })

    // Fires when a node is isolated
    socket.on('healing_triggered', data => {
      if (onHealingTriggered) onHealingTriggered(data)
    })

    socket.on('disconnect', () => {
      connected.current = false
      console.warn('[WS] Disconnected — mock data stays active')
    })

    socket.on('connect_error', () => {
      console.info('[WS] Backend not reachable — running in simulation mode')
    })

    socketRef.current = socket
    return () => socket.disconnect()
  }, [])

  return { socket: socketRef.current, isConnected: connected.current }
}
```

**Final App.jsx with real data hooks:**

```jsx
// src/App.jsx (WEEK 5+ VERSION — with real hooks)  [Windows]
import { useState, useCallback } from 'react'
import { useGraphData } from './hooks/useGraphData'
import { useWebSocket } from './hooks/useWebSocket'
import {
  MOCK_HEALING_EVENTS, MOCK_TIMELINE
} from './services/mockData'
// ... (same imports as before)

export default function App() {
  const {
    graphData, setGraphData,
    alerts, setAlerts,
    blocked, chainTxs, stats,
    isMockMode,
  } = useGraphData()

  const [healingEvents, setHealingEvents] = useState(MOCK_HEALING_EVENTS)
  const [healingNodeId, setHealingNodeId] = useState(null)
  const [timeline,      setTimeline]      = useState(MOCK_TIMELINE)
  const [use3D,         setUse3D]         = useState(true)

  // WebSocket handlers — these fire when REAL backend events arrive
  const handleGraphUpdate = useCallback(data => {
    setGraphData(data)
  }, [])

  const handleAlert = useCallback(alert => {
    // TODO: Prepend new alert to top of list
    setAlerts(prev => [alert, ...prev].slice(0, 50))
    setTimeline(prev => {
      const now = new Date().toLocaleTimeString()
      const last = prev[prev.length - 1]
      return [...prev, { time: now, threats: (last?.threats || 0) + 1, blocked: last?.blocked || 0 }]
    })
  }, [])

  const handleHealingTriggered = useCallback(event => {
    // Animate the isolated node
    setHealingNodeId(event.ip)
    setTimeout(() => setHealingNodeId(null), 3500)
    setHealingEvents(prev => [event, ...prev].slice(0, 10))
    // Update timeline
    setTimeline(prev => {
      const now = new Date().toLocaleTimeString()
      const last = prev[prev.length - 1]
      return [...prev, { time: now, threats: last?.threats || 0, blocked: (last?.blocked || 0) + 1 }]
    })
  }, [])

  useWebSocket({
    onGraphUpdate:      handleGraphUpdate,
    onAlert:            handleAlert,
    onHealingTriggered: handleHealingTriggered,
  })

  // ... (same JSX structure as Week 2 version, all state now from hooks)
}
```

**Week 5 Checkpoint:** Open browser → no CORS errors in console → `isMockMode = false` when backend runs.

---

### WEEK 6–7 — Polish + 2D Fallback + ForensicsModal

```jsx
// src/components/NetworkGraph2D/NetworkGraph2D.jsx  [Windows]
import React, { useRef, useEffect } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'

const STATUS_COLOR_2D = {
  normal: '#00ff88', suspicious: '#ffaa00', malicious: '#ff4444', blocked: '#0066ff'
}

export default function NetworkGraph2D({ graphData, healingNodeId }) {
  // Convert from react-force-graph format to Cytoscape format
  const elements = [
    ...graphData.nodes.map(n => ({
      data: {
        id: n.id, label: n.label,
        status: n.status, threat: n.threat_score
      }
    })),
    ...graphData.links.map(l => ({
      data: { id: `${l.source}-${l.target}`, source: l.source, target: l.target }
    })),
  ]

  const stylesheet = [
    {
      selector: 'node',
      style: {
        'background-color': ele => STATUS_COLOR_2D[ele.data('status')] || '#ffffff',
        'label': 'data(label)',
        'color': '#e2e8f0',
        'font-size': '10px',
        'font-family': 'monospace',
        'text-valign': 'bottom',
        'text-margin-y': 4,
        'width': 30, 'height': 30,
      }
    },
    {
      selector: 'edge',
      style: {
        'width': 1.5,
        'line-color': '#334466',
        'target-arrow-color': '#334466',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
      }
    },
  ]

  return (
    <CytoscapeComponent
      elements={elements}
      stylesheet={stylesheet}
      layout={{ name: 'cose' }}
      style={{ width: '100%', height: '100%', background: '#0a0e1a' }}
    />
  )
}
```

---

### WEEK 8 — Demo Hardening

```jsx
// Add to App.jsx — keyboard shortcut for demo
useEffect(() => {
  const handle = (e) => {
    if (e.key === 'F' && e.ctrlKey) {
      // Ctrl+F → simulate attack for demo
      const demoAlert = {
        id: `demo-${Date.now()}`,
        timestamp: new Date().toISOString(),
        source_ip: '10.0.0.2',
        attack_type: 'DDoS',
        severity: 'critical',
        threat_score: 0.94,
        description: 'DEMO: DDoS attack from 10.0.0.2',
        is_blocked: false,
        blockchain_tx: null,
      }
      handleAlert(demoAlert)
      setTimeout(() => {
        handleHealingTriggered({
          id: `heal-${Date.now()}`,
          ip: '10.0.0.2',
          attack_type: 'DDoS',
          trigger_score: 0.94,
          action: 'ISOLATED',
          edges_severed: 6,
          duration_ms: 312,
          network_stability_after: 94,
          timestamp: new Date().toISOString(),
        })
      }, 2000)
    }
  }
  window.addEventListener('keydown', handle)
  return () => window.removeEventListener('keydown', handle)
}, [handleAlert, handleHealingTriggered])
```

**Demo tip:** Press **Ctrl+F** during demo if live Mininet attack is slow to appear.

---

## FAILURE TRIAGE GUIDE

```
SYMPTOM: 3D graph is blank (black screen)
  → Fix: Check react-force-graph-3d version (pin to 1.x)
  → Fix: THREE.js version must be 0.167.x
  → Debug: Open DevTools console, look for THREE.js errors

SYMPTOM: CORS error in browser console
  → Fix: Verify vite.config.js proxy has /api and /socket.io targets
  → Fix: Restart Vite dev server after editing vite.config.js
  → Fix: Confirm backend runs on exactly port 8000

SYMPTOM: WebSocket keeps disconnecting
  → Fix: socket.io-client and server must be same major version (v4)
  → Fix: Check VITE_BACKEND_URL is http:// (not https://)
  → Debug: Network tab → WS → see frames

SYMPTOM: Animations lag during demo
  → Fix: Set linkDirectionalParticles to return 2 max (not 8)
  → Fix: Disable auto-camera rotation during demo to save frames
  → Fix: Use 2D mode (Cytoscape) as fallback

SYMPTOM: Mock data not matching backend response shape
  → Fix: Compare against docs/DATA_SCHEMAS.md
  → The mock data structures in mockData.js MUST match exact API shapes
  → If shapes differ, update mockData.js (not the components)

SYMPTOM: Node colors not updating in real-time
  → Fix: Ensure setGraphData creates a NEW object reference
  → BAD:  graphData.nodes[0].status = 'malicious'
  → GOOD: setGraphData({...data, nodes: [...data.nodes]})
```
