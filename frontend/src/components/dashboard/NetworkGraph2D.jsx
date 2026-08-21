// [Windows] GraphSentinel — Susheep
// NetworkGraph2D — updated with healing animation and new token colors
// Status is differentiated by: color + border style + node size (not color alone)
import { useRef, useEffect, useMemo } from 'react'
import cytoscape from 'cytoscape'
import { STATUS_COLORS } from '../../constants/theme'

export default function NetworkGraph2D({ graphData, healingNodeId, onNodeClick }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  // Ref so the tap handler always calls the latest callback without forcing
  // cytoscape to be torn down and rebuilt (which onNodeClick's inline arrow
  // function identity would otherwise trigger on every parent render).
  const onNodeClickRef = useRef(onNodeClick)
  onNodeClickRef.current = onNodeClick

  const elements = useMemo(() => {
    const nodes = graphData.nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.label,
        status: n.status,
        threat: n.threat_score,
        is_blocked: n.is_blocked,
        source: n.source,
      },
    }))
    const edges = graphData.links.map((l) => ({
      data: {
        id: `${typeof l.source === 'object' ? l.source.id : l.source}-${typeof l.target === 'object' ? l.target.id : l.target}`,
        source: typeof l.source === 'object' ? l.source.id : l.source,
        target: typeof l.target === 'object' ? l.target.id : l.target,
        value: l.value || 0.5,
      },
    }))
    return [...nodes, ...edges]
  }, [graphData])

  useEffect(() => {
    if (!containerRef.current) return

    // Destroy previous instance
    if (cyRef.current) {
      try { cyRef.current.destroy() } catch { /* ignore */ }
      cyRef.current = null
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        // Base node style — shape encodes status (accessibility: not color alone)
        {
          selector: 'node',
          style: {
            'background-color': (ele) => STATUS_COLORS[ele.data('status')] || '#4F6EF7',
            label: 'data(label)',
            color: '#8A95B0',
            'font-size': '9px',
            'font-family': '"DM Mono", monospace',
            'text-valign': 'bottom',
            'text-margin-y': 5,
            'text-outline-width': 0,
            width: 24,
            height: 24,
            shape: 'ellipse', // default: circle = normal
            'border-width': 1.5,
            'border-color': (ele) => STATUS_COLORS[ele.data('status')] + '40' || '#262D3F',
          },
        },
        // Normal — circle (default above)

        // Suspicious — diamond shape
        {
          selector: 'node[status="suspicious"]',
          style: {
            shape: 'diamond',
            width: 28,
            height: 28,
            'border-color': '#E8922A',
            'border-width': 2,
          },
        },

        // Malicious — triangle (warning shape)
        {
          selector: 'node[status="malicious"]',
          style: {
            shape: 'triangle',
            width: 36,
            height: 36,
            'border-color': '#E03C3C',
            'border-width': 2.5,
          },
        },

        // Blocked — hexagon (containment shape) with dashed border
        {
          selector: 'node[status="blocked"]',
          style: {
            shape: 'hexagon',
            width: 30,
            height: 30,
            'border-color': '#4F6EF7',
            'border-width': 2,
            'border-style': 'dashed',
            opacity: 0.8,
          },
        },

        // Configured baseline host with no traffic seen yet — dim + dashed,
        // so the topology's placeholder hosts read as distinct from hosts
        // that actually appeared in captured traffic (Error.md #9). Applied
        // last so it layers on top of the status-shape rules above rather
        // than replacing them.
        {
          selector: 'node[source="configured"]',
          style: {
            opacity: 0.35,
            'border-style': 'dashed',
          },
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
              return v > 0.75 ? '#E03C3C55' : v > 0.5 ? '#E8922A44' : '#262D3F'
            },
            'target-arrow-color': '#3D4560',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
      ],
      layout: { name: 'cose', animate: false },
    })

    // Cytoscape's own node.data() only carries the trimmed fields mapped
    // into `elements` above — look the full node back up in graphData so
    // the detail panel gets the same complete shape NetworkGraph3D already
    // passes (connections, bytes_total, attack_type, source, etc.), not a
    // partial object with mismatched field names (Error.md follow-up: this
    // view previously had no click handler at all).
    cy.on('tap', 'node', (evt) => {
      const fullNode = graphData.nodes.find((n) => n.id === evt.target.id())
      if (fullNode) onNodeClickRef.current?.(fullNode)
    })

    cyRef.current = cy

    return () => {
      if (cyRef.current) {
        try { cyRef.current.destroy() } catch { /* ignore */ }
        cyRef.current = null
      }
    }
  }, [elements, graphData])

  // Healing animation: highlight the healing node with a pulsing style
  useEffect(() => {
    if (!cyRef.current || !healingNodeId) return

    const node = cyRef.current.getElementById(healingNodeId)
    if (!node || node.empty()) return

    // Add healing highlight class
    node.addClass('healing')

    // Override style temporarily
    node.style({
      'border-color': '#4F6EF7',
      'border-width': 4,
      'border-style': 'solid',
      'background-color': '#4F6EF780',
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
      style={{ background: '#141414' }}
      role="img"
      aria-label="2D network graph showing node connections and threat status"
    />
  )
}
