// [Windows] GraphSentinel — Susheep
import CytoscapeComponent from 'react-cytoscapejs'
import { STATUS_COLORS } from '../../constants/theme'

export default function NetworkGraph2D({ graphData }) {
  const elements = [
    ...graphData.nodes.map((n) => ({
      data: { id: n.id, label: n.label, status: n.status, threat: n.threat_score },
    })),
    ...graphData.links.map((l) => ({
      data: {
        id: `${typeof l.source === 'object' ? l.source.id : l.source}-${typeof l.target === 'object' ? l.target.id : l.target}`,
        source: typeof l.source === 'object' ? l.source.id : l.source,
        target: typeof l.target === 'object' ? l.target.id : l.target,
      },
    })),
  ]

  const stylesheet = [
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
  ]

  return (
    <CytoscapeComponent
      elements={elements}
      stylesheet={stylesheet}
      layout={{ name: 'cose', animate: true, animationDuration: 500 }}
      style={{ width: '100%', height: '100%', background: '#0a0e1a' }}
    />
  )
}
