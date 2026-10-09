// [Windows] GraphSentinel — Susheep
// useNodeHierarchy — merges live threat data into the static pyramid hierarchy
// Flatten the hierarchy tree into a lookup map { ip → node }
function buildIpMap(node, map = {}) {
  if (!node) return map
  if (node.ip) map[node.ip] = node
  if (node.children) node.children.forEach((c) => buildIpMap(c, map))
  return map
}

// Build ancestor path from a node up to root (inclusive)
function buildAncestorPath(targetId, node, path = []) {
  if (!node) return null
  if (node.id === targetId) return [...path, node]
  for (const child of node.children || []) {
    const found = buildAncestorPath(targetId, child, [...path, node])
    if (found) return found
  }
  return null
}

// Merge live threat statuses into the hierarchy nodes
function mergeStatuses(node, statusMap) {
  if (!node) return null
  const overrideStatus = statusMap[node.ip] || statusMap[node.id]
  return {
    ...node,
    status: overrideStatus || node.status,
    children: (node.children || []).map((c) => mergeStatuses(c, statusMap)),
  }
}

import { useMemo } from 'react'
import useGraphStore from '../store/useGraphStore'
import { currentlyBlocked, deriveStatusMap } from '../utils/hierarchyStatus'

// Error.md #2: there is no real org-chart data source (department/role
// assignments aren't derivable from network flows) — the previous hardcoded
// tree referenced IPs that don't even exist in the configured topology
// (10.0.0.11 on a 10-host network). Building the pyramid directly from live
// graphData means every node it shows genuinely exists on the network,
// instead of a fabricated org structure that could silently diverge from
// reality.
function buildHierarchyFromGraph(graphData) {
  const nodes = graphData?.nodes || []
  if (nodes.length === 0) return null
  return {
    id: 'root',
    label: 'Network Root',
    sublabel: `${nodes.length} hosts`,
    level: 0,
    ip: null,
    status: 'normal',
    children: nodes.map((node) => ({
      id: node.id,
      label: node.label || node.id,
      sublabel: node.id,
      level: 1,
      ip: node.id,
      status: node.status,
      source: node.source,
      children: [],
    })),
  }
}

export function useNodeHierarchy(alerts = [], healingEvents = []) {
  const nodeOverrides = useGraphStore((s) => s.nodeOverrides)
  const graphData = useGraphStore((s) => s.graphData)
  const blockedIPs = useGraphStore((s) => s.blockedIPs)
  const orgHierarchy = useMemo(() => buildHierarchyFromGraph(graphData), [graphData])

  // What is blocked NOW, not what was ever blocked: the healing feed is history.
  const blockedNow = useMemo(() => currentlyBlocked(graphData, blockedIPs), [graphData, blockedIPs])

  const statusMap = useMemo(
    () => deriveStatusMap({ alerts, healingEvents, nodeOverrides, blockedNow }),
    [alerts, healingEvents, nodeOverrides, blockedNow],
  )

  const ipMap = useMemo(() => buildIpMap(orgHierarchy), [orgHierarchy])

  const enrichedHierarchy = useMemo(() => {
    return mergeStatuses(orgHierarchy, statusMap)
  }, [statusMap, orgHierarchy])

  // Compute attack paths for nodes in 'attacking' state
  const attackPaths = useMemo(() => {
    return Object.entries(statusMap)
      .filter(([, status]) => status === 'attacking')
      .map(([ip]) => {
        const node = ipMap[ip]
        if (!node) return null
        const path = buildAncestorPath(node.id, orgHierarchy)
        return { sourceIp: ip, path }
      })
      .filter(Boolean)
  }, [statusMap, ipMap, orgHierarchy])

  const findNodeByIp = (ip) => ipMap[ip] || null

  const isLateralMovement = (threat) => {
    const src = findNodeByIp(threat.source_ip)
    const tgt = findNodeByIp(threat.targetIp || threat.source_ip)
    if (!src || !tgt) return false
    return tgt.level < src.level
  }

  return { enrichedHierarchy, attackPaths, statusMap, findNodeByIp, isLateralMovement }
}
