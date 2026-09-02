// [Windows] GraphSentinel — Susheep
// NetworkGraph2D — updated with healing animation and new token colors
// Status is differentiated by: color + border style + node size (not color alone)
import { useRef, useEffect, useMemo } from 'react'
import cytoscape from 'cytoscape'
import { STATUS_COLORS } from '../../constants/theme'

export default function NetworkGraph2D({ graphData, healingNodeId, onNodeClick }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const onNodeClickRef = useRef(onNodeClick)
  onNodeClickRef.current = onNodeClick

  const graphDataRef = useRef(graphData)
  useEffect(() => {
    graphDataRef.current = graphData
  }, [graphData])

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

    const cy = cytoscape({
      container: containerRef.current,
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
            'border-color': (ele) => STATUS_COLORS[ele.data('status')] || '#262D3F',
            'border-opacity': 0.25,
          },
        },
        // Suspicious — diamond shape
        {
          selector: 'node[status="suspicious"]',
          style: { shape: 'diamond', width: 28, height: 28, 'border-color': '#E8922A', 'border-width': 2 },
        },
        // Malicious — triangle (warning shape)
        {
          selector: 'node[status="malicious"]',
          style: { shape: 'triangle', width: 36, height: 36, 'border-color': '#E03C3C', 'border-width': 2.5 },
        },
        // Blocked — hexagon (containment shape) with dashed border
        {
          selector: 'node[status="blocked"]',
          style: { shape: 'hexagon', width: 30, height: 30, 'border-color': '#4F6EF7', 'border-width': 2, 'border-style': 'dashed', opacity: 0.8 },
        },
        // Configured baseline host
        {
          selector: 'node[source="configured"]',
          style: { opacity: 0.35, 'border-style': 'dashed' },
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
              return v > 0.75 ? '#E03C3C' : v > 0.5 ? '#E8922A' : '#262D3F'
            },
            'line-opacity': (ele) => {
              const v = ele.data('value') || 0.5
              return v > 0.75 ? 0.33 : v > 0.5 ? 0.27 : 1
            },
            'target-arrow-color': '#3D4560',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
      ],
      layout: { 
        name: 'concentric', 
        animate: false,
        concentric: (node) => {
          const ipMatch = node.id().match(/\.(\d+)$/)
          return 255 - (ipMatch ? parseInt(ipMatch[1], 10) : 100)
        },
        levelWidth: () => 1
      },
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

    const newCount = elements.filter(e => !e.data.source && !e.data.target).length
    if (newCount !== nodeCountRef.current) {
      cy.layout({
        name: 'concentric',
        animate: true,
        animationDuration: 300,
        concentric: (node) => {
          const ipMatch = node.id().match(/\.(\d+)$/)
          return 255 - (ipMatch ? parseInt(ipMatch[1], 10) : 100)
        },
        levelWidth: () => 1
      }).run()
      nodeCountRef.current = newCount
    }
  }, [elements])

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
      'background-color': '#4F6EF7',
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
      style={{ background: '#141414' }}
      role="img"
      aria-label="2D network graph showing node connections and threat status"
    />
  )
}
