// [Windows] GraphSentinel — Susheep
import { useRef, useEffect, useMemo } from 'react'
import cytoscape from 'cytoscape'
import { STATUS_COLORS } from '../../constants/theme'

export default function NetworkGraph2D({ graphData, healingNodeId }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)

  const elements = useMemo(() => {
    const nodes = graphData.nodes.map((n) => ({
      data: { id: n.id, label: n.label, status: n.status, threat: n.threat_score },
    }))
    const edges = graphData.links.map((l) => ({
      data: {
        id: `${typeof l.source === 'object' ? l.source.id : l.source}-${typeof l.target === 'object' ? l.target.id : l.target}`,
        source: typeof l.source === 'object' ? l.source.id : l.source,
        target: typeof l.target === 'object' ? l.target.id : l.target,
      },
    }))
    return [...nodes, ...edges]
  }, [graphData])

  useEffect(() => {
    if (!containerRef.current) return

    // Destroy previous instance
    if (cyRef.current) {
      try { cyRef.current.destroy() } catch {}
      cyRef.current = null
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele) => STATUS_COLORS[ele.data('status')] || '#ffffff',
            label: 'data(label)',
            color: '#e2e8f0',
            'font-size': '10px',
            'font-family': 'monospace',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            width: 30,
            height: 30,
          },
        },
        {
          selector: 'node[status="malicious"]',
          style: {
            'border-color': '#ff0000',
            'border-width': 3,
            width: 40,
            height: 40,
          },
        },
        {
          selector: 'node[status="blocked"]',
          style: {
            'border-color': '#0066ff',
            'border-width': 3,
            'border-style': 'dashed',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': '#334466',
            'target-arrow-color': '#334466',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
      ],
      layout: { name: 'cose', animate: false },
    })

    cyRef.current = cy

    return () => {
      if (cyRef.current) {
        try { cyRef.current.destroy() } catch {}
        cyRef.current = null
      }
    }
  }, [elements])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', background: '#0a0e1a' }}
    />
  )
}
