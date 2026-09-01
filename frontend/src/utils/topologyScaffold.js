// [Windows] GraphSentinel — Susheep
// topologyScaffold — guarantees the Network Topology view always renders a
// readable network shape instead of a scatter of disconnected dots.
//
// The backend's /api/v1/graph only emits edges for *observed traffic* flows,
// so with the pipeline idle (no Mininet capture, no simulation running) the
// response is 10 hosts and zero links. That rendered as ten nodes drifting
// apart with nothing joining them — indistinguishable from "broken".
//
// This overlays the *configured* physical topology from
// mininet/topologies/base_topology.py — an OVS controller (c0) driving one
// switch (s1) in a star with hosts h1..h10 — as scaffold nodes/edges.
// Real traffic links from the backend are kept and drawn on top, so an
// attack path still stands out against the baseline star.

const IPV4 = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/

const SWITCH_ID = 's1'
const CONTROLLER_ID = 'c0'

const endpointId = (e) => (e && typeof e === 'object' ? e.id : e)

export function withTopologyScaffold(graphData) {
  const nodes = graphData?.nodes ?? []
  const links = graphData?.links ?? []

  if (nodes.length === 0) return { nodes: [], links: [] }

  const hostNodes = nodes.filter((n) => IPV4.test(String(n.id)))
  // Nothing recognisable to build a star around — leave the data untouched.
  if (hostNodes.length === 0) return { nodes, links }

  // If the backend ever starts returning infrastructure nodes itself, defer
  // to it entirely rather than double-adding a switch.
  if (nodes.some((n) => n.id === SWITCH_ID || n.kind === 'switch')) {
    return { nodes, links }
  }

  const anyMalicious = hostNodes.some((n) => n.status === 'malicious')

  const scaffoldNodes = [
    {
      id: CONTROLLER_ID,
      label: 'c0',
      kind: 'controller',
      status: 'normal',
      threat_score: 0,
      connections: 1,
      source: 'configured',
    },
    {
      id: SWITCH_ID,
      label: 's1',
      kind: 'switch',
      // The switch is infrastructure, not a host — it never carries a threat
      // score. Flag degraded only so the operator sees the fabric is under load.
      status: anyMalicious ? 'suspicious' : 'normal',
      threat_score: 0,
      connections: hostNodes.length,
      source: 'configured',
    },
  ]

  const seen = new Set(
    links.map((l) => `${endpointId(l.source)}::${endpointId(l.target)}`)
  )
  const has = (a, b) => seen.has(`${a}::${b}`) || seen.has(`${b}::${a}`)

  const infraLinks = [
    {
      source: CONTROLLER_ID,
      target: SWITCH_ID,
      value: 0,
      attack_type: null,
      kind: 'infra',
      packet_count: 0,
    },
  ]
  for (const host of hostNodes) {
    if (has(SWITCH_ID, host.id)) continue
    infraLinks.push({
      source: SWITCH_ID,
      target: host.id,
      value: 0,
      attack_type: null,
      kind: 'infra',
      packet_count: 0,
    })
  }

  return {
    nodes: [...scaffoldNodes, ...nodes],
    links: [...infraLinks, ...links],
  }
}
