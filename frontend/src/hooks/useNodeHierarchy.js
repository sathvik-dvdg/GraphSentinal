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

export function useNodeHierarchy(alerts = [], healingEvents = []) {
  const nodeOverrides = useGraphStore((s) => s.nodeOverrides)
  const orgHierarchy = useGraphStore((s) => s.orgHierarchy)

  const statusMap = useMemo(() => {
    const map = {}

    // Healing events → isolated
    healingEvents.forEach((ev) => {
      if (ev.action === 'ISOLATED') {
        map[ev.ip] = 'isolated'
      }
    })

    // Critical non-isolated alerts → attacking or infected
    alerts.forEach((alert) => {
      const ip = alert.source_ip
      if (map[ip] === 'isolated') return // already isolated
      if (alert.severity === 'critical' && !alert.is_blocked) {
        map[ip] = 'attacking'
      } else if (alert.severity === 'warning' && !map[ip]) {
        map[ip] = 'infected'
      }
    })

    // Apply manual node overrides
    Object.entries(nodeOverrides).forEach(([ip, status]) => {
      if (status === 'normal') {
        delete map[ip] // Fallback to node.status in ORG_HIERARCHY
      } else if (status) {
        map[ip] = status
      }
    })

    return map
  }, [alerts, healingEvents, nodeOverrides])

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
