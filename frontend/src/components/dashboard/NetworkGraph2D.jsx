// [Windows] GraphSentinel — Susheep
// NetworkGraph2D — updated with healing animation and new token colors
// Status is differentiated by: color + border style + node size (not color alone)
import { useRef, useEffect, useMemo, useCallback } from 'react'
import cytoscape from 'cytoscape'
import { STATUS_COLORS } from '../../constants/theme'

const LAYOUT = {
  name: 'concentric',
  minNodeSpacing: 46,
  fit: true,
  padding: 40,
  // Infrastructure (switch / controller) in the centre, hosts on the outer ring.
  concentric: (node) => (node.data('kind') && node.data('kind') !== 'host' ? 10 : 1),
  levelWidth: () => 1,
}

export default function NetworkGraph2D({ graphData, healingNodeId, onNodeClick }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const onNodeClickRef = useRef(onNodeClick)
  const graphDataRef = useRef(graphData)
  useEffect(() => {
    onNodeClickRef.current = onNodeClick
    graphDataRef.current = graphData
  }, [onNodeClick, graphData])

  const elements = useMemo(() => {
    const nodes = graphData.nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.label,
        status: n.status,
        threat: n.threat_score,
        is_blocked: n.is_blocked,
        source: n.source,
        kind: n.kind || 'host',
      },
    }))
    const edges = graphData.links.map((l) => ({
      data: {
        id: `${typeof l.source === 'object' ? l.source.id : l.source}-${typeof l.target === 'object' ? l.target.id : l.target}`,
        source: typeof l.source === 'object' ? l.source.id : l.source,
        target: typeof l.target === 'object' ? l.target.id : l.target,
        value: l.value || (l.kind === 'infra' ? 0 : 0.5),
        kind: l.kind || 'traffic',
      },
    }))
    return [...nodes, ...edges]
  }, [graphData])

  useEffect(() => {
    if (!containerRef.current) return

    const cy = cytoscape({
      container: containerRef.current,
      style: [
        // Base node style — shape encodes status (accessibility: not color alone)
        {
          selector: 'node',
          style: {
            'background-color': (ele) => STATUS_COLORS[ele.data('status')] || '#3b56d9',
            label: 'data(label)',
            color: '#5a616e',
            'font-size': '9px',
            'font-family': '"DM Mono", monospace',
            'text-valign': 'bottom',
            'text-margin-y': 5,
            'text-outline-width': 0,
            width: 24,
            height: 24,
            shape: 'ellipse', // default: circle = normal
            'border-width': 1.5,
            'border-color': (ele) => STATUS_COLORS[ele.data('status')] || '#e2e5ea',
            'border-opacity': 0.25,
          },
        },
        // Suspicious — diamond shape
        {
          selector: 'node[status="suspicious"]',
          style: { shape: 'diamond', width: 28, height: 28, 'border-color': '#b7791f', 'border-width': 2 },
        },
        // Malicious — triangle (warning shape)
        {
          selector: 'node[status="malicious"]',
          style: { shape: 'triangle', width: 36, height: 36, 'border-color': '#E03C3C', 'border-width': 2.5 },
        },
        // Blocked — hexagon (containment shape) with dashed border
        {
          selector: 'node[status="blocked"]',
          style: { shape: 'hexagon', width: 30, height: 30, 'border-color': '#3b56d9', 'border-width': 2, 'border-style': 'dashed', opacity: 0.8 },
        },
        // Configured baseline host — dimmed (no traffic seen yet)
        {
          selector: 'node[source="configured"]',
          style: { opacity: 0.5, 'border-style': 'dashed' },
        },
        // Edges
        {
          selector: 'edge',
          style: {
            width: (ele) => {
              const v = ele.data('value') || 0.5
              return v > 0.75 ? 2.5 : v > 0.5 ? 1.5 : 1
            },
            'line-color': (ele) => {
              const v = ele.data('value') || 0.5
              return v > 0.75 ? '#E03C3C' : v > 0.5 ? '#b7791f' : '#c7cbd2'
            },
            'line-opacity': (ele) => {
              const v = ele.data('value') || 0.5
              return v > 0.75 ? 0.5 : v > 0.5 ? 0.4 : 0.9
            },
            'target-arrow-color': '#9aa1ad',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
        // ── Configured star infrastructure (from base_topology.py) ──
        // OVS switch s1 — solid rounded square, central hub of the star
        {
          selector: 'node[kind="switch"]',
          style: {
            shape: 'round-rectangle', width: 46, height: 30,
            'background-color': '#3b56d9', 'background-opacity': 1,
            'border-color': '#2c40a8', 'border-width': 1.5, 'border-opacity': 1,
            'border-style': 'solid', opacity: 1,
            color: '#3b56d9', 'font-size': '10px', 'font-weight': 'bold',
          },
        },
        // OpenFlow controller c0 — small neutral diamond above the switch
        {
          selector: 'node[kind="controller"]',
          style: {
            shape: 'diamond', width: 22, height: 22,
            'background-color': '#5a616e', 'background-opacity': 1,
            'border-color': '#41474f', 'border-width': 1.5, 'border-opacity': 1,
            'border-style': 'solid', opacity: 1,
            color: '#5a616e', 'font-size': '9px',
          },
        },
        // Infra links — thin, quiet, no arrowhead
        {
          selector: 'edge[kind="infra"]',
          style: {
            width: 1.5, 'line-color': '#c7cbd2', 'line-opacity': 0.9,
            'target-arrow-shape': 'none', 'curve-style': 'straight',
          },
        },
      ],
      layout: { ...LAYOUT, animate: false },
      elements: [] // start empty, updated by next effect
    })

    cy.on('tap', 'node', (evt) => {
      const fullNode = graphDataRef.current?.nodes.find((n) => n.id === evt.target.id())
      if (fullNode) onNodeClickRef.current?.(fullNode)
    })

    cyRef.current = cy
    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, []) // initialize once

  const nodeCountRef = useRef(0)

  const relayout = useCallback((animate) => {
    const cy = cyRef.current
    if (!cy || cy.destroyed()) return
    const el = containerRef.current
    // Cytoscape caches the container size; if it initialised before the panel
    // had a height (grid cell with minHeight:0), every node collapses onto the
    // origin. Re-sync the size before laying out.
    if (el && el.clientWidth > 0 && el.clientHeight > 0) cy.resize()
    if (cy.nodes().length === 0) return
    cy.layout({ ...LAYOUT, animate, animationDuration: 300 }).run()
  }, [])

  // Keep the canvas sized to its panel and re-run the layout on resize —
  // mirrors the explicit sizing NetworkGraph3D needs for the same reason.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    let first = true
    const obs = new ResizeObserver(() => {
      relayout(!first)
      first = false
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [relayout])

  // Update elements in place without destroying the instance
  useEffect(() => {
    if (!cyRef.current) return
    const cy = cyRef.current

    cy.batch(() => {
      const currentIds = new Set(elements.map(e => e.data.id))
      // Remove stale
      cy.elements().forEach(ele => {
        if (!currentIds.has(ele.id())) cy.remove(ele)
      })
      // Add or update
      elements.forEach(ele => {
        const existing = cy.getElementById(ele.data.id)
        if (existing.length > 0) {
          existing.data(ele.data)
        } else {
          cy.add(ele)
        }
      })
    })

    // Count real nodes: edges always carry data.target, nodes never do.
    // (The previous check keyed on data.source, which every node now sets to
    // 'observed'/'configured' — so it was always 0 and the concentric layout
    // never ran, leaving every node stacked at the origin.)
    const newCount = elements.filter(e => e.data.target === undefined).length
    if (newCount !== nodeCountRef.current) {
      relayout(nodeCountRef.current !== 0)
      nodeCountRef.current = newCount
    }
  }, [elements, relayout])

  // Healing animation: highlight the healing node with a pulsing style
  useEffect(() => {
    if (!cyRef.current || !healingNodeId) return

    const node = cyRef.current.getElementById(healingNodeId)
    if (!node || node.empty()) return

    // Add healing highlight class
    node.addClass('healing')

    // Override style temporarily
    node.style({
      'border-color': '#3b56d9',
      'border-width': 4,
      'border-style': 'solid',
      'background-color': '#3b56d9',
      'background-opacity': 0.5,
    })

    const t = setTimeout(() => {
      if (cyRef.current && !cyRef.current.destroyed()) {
        node.removeStyle()
        node.removeClass('healing')
      }
    }, 3000)

    return () => clearTimeout(t)
  }, [healingNodeId])

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      style={{ background: '#ffffff' }}
      role="img"
      aria-label="2D network graph showing node connections and threat status"
    />
  )
}
