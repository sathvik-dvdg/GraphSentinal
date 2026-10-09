// [Windows] GraphSentinel
// NetworkTopology -- the state of the network at a glance, then the detail.
// The page opens with a sentence ("No active threats. 3 of 10 hosts are
// isolated."), counts the hosts by state, and puts the hosts that need a look in
// a list beside the map. Selecting a host anywhere (map, 3D, tree, list) opens
// the same panel: why it is in its state, what the system did, what you can do.
import { useMemo, useState } from 'react'
import { Network } from 'lucide-react'
import useGraphStore from '../store/useGraphStore'
import { useNodeHierarchy } from '../hooks/useNodeHierarchy'
import NetworkGraph2D from '../components/dashboard/NetworkGraph2D'
import HostHierarchy from '../components/topology/HostHierarchy'
import HostScene3D from '../components/topology/HostScene3D'
import StateTiles from '../components/topology/StateTiles'
import AttentionTable from '../components/topology/AttentionTable'
import SelectedHostPanel from '../components/topology/SelectedHostPanel'
import ActivityLog from '../components/topology/ActivityLog'
import ErrorBoundary from '../components/shared/ErrorBoundary'
import ConnectionModeBadge from '../components/ui/ConnectionModeBadge'
import DataFreshnessBadge from '../components/ui/DataFreshnessBadge'
import { withTopologyScaffold } from '../utils/topologyScaffold'
import { buildHosts, countStates, describeNetwork, HOST_STATES } from '../utils/hostState'
import { GS } from '../constants/colors'

const VIEWS = [
  { id: 'map', label: 'Map' },
  { id: 'hierarchy', label: 'Hierarchy' },
  { id: '3d', label: '3D' },
]

const VIEW_NOTE = {
  map: 'Every host reaches the network through switch s1. The controller c0 tells s1 what to allow.',
  hierarchy: 'The network, its switch, and the hosts grouped by state.',
  '3d': 'Hosts stand around switch s1. Rotate to see the ones at the back, and select a host to read about it.',
}

export default function NetworkTopology() {
  const [view, setView] = useState('map')
  const [pickedId, setPickedId] = useState(null)
  const { graphData, healingNodeId, connectionMode, socketStatus, dataErrors, alerts, healingEvents } = useGraphStore()
  const { enrichedHierarchy } = useNodeHierarchy(alerts, healingEvents)

  const hosts = useMemo(() => buildHosts(enrichedHierarchy?.children, graphData.nodes), [enrichedHierarchy, graphData.nodes])
  const counts = useMemo(() => countStates(hosts), [hosts])
  const { headline, detail } = useMemo(() => describeNetwork(hosts), [hosts])

  // Overlay the configured star (c0 -> s1 -> hosts) so the graph is never a
  // disconnected scatter when the pipeline is idle, and give every host the one
  // status the whole page agrees on (alerts, healing feed and blocked set merged).
  const graph = useMemo(() => {
    const scaffolded = withTopologyScaffold(graphData)
    const byId = new Map(hosts.map((h) => [h.id, h]))
    return {
      ...scaffolded,
      nodes: scaffolded.nodes.map((n) => {
        const host = !n.kind && byId.get(n.id)
        return host ? { ...n, status: HOST_STATES[host.state].graphStatus, is_blocked: host.isBlocked } : n
      }),
    }
  }, [graphData, hosts])

  // With nothing picked, open the first host that needs a look.
  const firstToCheck = hosts.find((h) => h.state !== 'healthy')
  const selectedId = hosts.some((h) => h.id === pickedId) ? pickedId : (firstToCheck?.id ?? null)
  const selected = hosts.find((h) => h.id === selectedId) ?? null

  // Scaffold nodes (the switch, the controller) are not hosts.
  const handleNodeClick = (node) => {
    if (node?.kind) return
    setPickedId(node.id)
  }

  const hasTopology = graph.nodes.length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 1440 }}>
      <header className="gs-rise" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxWidth: 780 }}>
          <h1 style={{ fontSize: 34, lineHeight: '40px', textWrap: 'balance' }}>{headline}</h1>
          <p style={{ fontSize: 15, lineHeight: '22px', color: GS.textMuted, maxWidth: '65ch' }}>{detail}</p>
          <div><DataFreshnessBadge dataErrors={{ graph: dataErrors.graph }} /></div>
        </div>
        <div className="gs-seg" role="group" aria-label="Topology view">
          {VIEWS.map((v) => (
            <button key={v.id} type="button" className="gs-seg-item" aria-pressed={view === v.id} onClick={() => setView(v.id)}>
              {v.label}
            </button>
          ))}
        </div>
      </header>

      <StateTiles hosts={hosts} counts={counts} />

      <div className="gs-topo-layout">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24, minWidth: 0 }}>
          <section className="gs-panel gs-rise" style={{ '--i': 4, overflow: 'hidden' }} aria-label="Network view">
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '14px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700 }}>{VIEWS.find((v) => v.id === view).label}</h2>
                <p style={{ fontSize: 13, color: GS.textMuted, maxWidth: '62ch' }}>{VIEW_NOTE[view]}</p>
              </div>
              <ConnectionModeBadge mode={connectionMode} socketStatus={socketStatus} />
            </div>

            <div style={{ position: 'relative', height: view === 'map' ? 'clamp(400px, 56vh, 600px)' : 'auto', minHeight: view === 'hierarchy' ? 360 : undefined }}>
              {!hasTopology ? (
                <TopologyEmptyState connectionMode={connectionMode} />
              ) : view === 'hierarchy' ? (
                <HostHierarchy hosts={hosts} selectedId={selectedId} onSelect={setPickedId} />
              ) : view === '3d' ? (
                <HostScene3D hosts={hosts} selectedId={selectedId} onSelect={setPickedId} />
              ) : (
                <ErrorBoundary label="The network map">
                  <NetworkGraph2D graphData={graph} healingNodeId={healingNodeId} onNodeClick={handleNodeClick} selectedId={selectedId} />
                </ErrorBoundary>
              )}
            </div>

            {view === 'map' && hasTopology && <MapKey />}
          </section>

          <AttentionTable hosts={hosts} events={healingEvents} selectedId={selectedId} onSelect={setPickedId} />
        </div>

        <aside style={{ display: 'flex', flexDirection: 'column', gap: 24, minWidth: 0 }}>
          <SelectedHostPanel host={selected} events={healingEvents} />
          <ActivityLog events={healingEvents} hosts={hosts} />
        </aside>
      </div>
    </div>
  )
}

// What each node shape and line on the map means. The shapes are drawn by the
// graph itself (circle, diamond, triangle, hexagon), so this must match it.
function MapKey() {
  const item = { display: 'inline-flex', alignItems: 'center', gap: 8 }
  return (
    <ul style={{ listStyle: 'none', display: 'flex', flexWrap: 'wrap', gap: '8px 20px', padding: '12px 20px', borderTop: '1px solid var(--border-subtle)', fontSize: 13, color: GS.textBody }} aria-label="Map key">
      <li style={item}><Shape d="M8 1.5a6.5 6.5 0 1 0 0 13a6.5 6.5 0 0 0 0-13z" stroke={GS.success} />Circle: healthy</li>
      <li style={item}><Shape d="M8 1L15 8L8 15L1 8z" stroke={GS.warn} />Diamond: watching</li>
      <li style={item}><Shape d="M8 1.5L15 14.5H1z" stroke={GS.danger} />Triangle: active threat</li>
      <li style={item}><Shape d="M4.5 2h7L15 8l-3.5 6h-7L1 8z" stroke={GS.text} dash="2.5 2" />Hexagon: isolated</li>
      <li style={item}>
        <svg width="28" height="8" viewBox="0 0 28 8" aria-hidden="true"><path d="M0 4H28" stroke={GS.danger} strokeWidth="2" strokeDasharray="5 4" fill="none" /></svg>
        Dashed red link: cut at s1
      </li>
    </ul>
  )
}

function Shape({ d, stroke, dash }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d={d} fill="none" stroke={stroke} strokeWidth="1.6" strokeDasharray={dash} strokeLinejoin="round" />
    </svg>
  )
}

function TopologyEmptyState({ connectionMode }) {
  const offline = connectionMode === 'mock' || connectionMode === 'offline' || connectionMode === 'connecting'
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, padding: 24, textAlign: 'center' }}>
      <div style={{ width: 44, height: 44, borderRadius: 10, border: '1px solid var(--border-panel)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: GS.textMuted }}>
        <Network size={20} aria-hidden="true" />
      </div>
      <p style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 500 }}>
        {offline ? 'The backend is offline, so there is no live topology.' : 'Waiting for the first graph snapshot.'}
      </p>
      <p style={{ fontSize: 14, lineHeight: '21px', color: GS.textMuted, maxWidth: 360 }}>
        {offline
          ? 'No hosts to show: the backend is not answering. Start it, and the network appears here.'
          : 'No hosts detected yet. Start the monitor to populate the map.'}
      </p>
    </div>
  )
}
