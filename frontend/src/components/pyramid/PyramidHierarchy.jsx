// [Windows] GraphSentinel — Susheep
// PyramidHierarchy — SVG org tree layout using d3-hierarchy for math only
// No d3 DOM manipulation — all rendering is React JSX SVG
import { useMemo, useState } from 'react'
import { hierarchy, tree } from 'd3-hierarchy'
import { STATUS_COLORS } from './pyramidConfig'
import NodeInspector from './NodeInspector'
import { useNodeHierarchy } from '../../hooks/useNodeHierarchy'
import useGraphStore from '../../store/useGraphStore'

const NODE_W = 130
const NODE_H = 52
const LEVEL_GAP = 80
const H_GAP = 20

export default function PyramidHierarchy() {
  const [selectedNode, setSelectedNode] = useState(null)

  const alerts = useGraphStore((s) => s.alerts)
  const healingEvents = useGraphStore((s) => s.healingEvents)

  const { enrichedHierarchy, attackPaths } = useNodeHierarchy(alerts, healingEvents)

  // Build d3 layout from the enriched hierarchy
  const { nodes, links, svgWidth, svgHeight } = useMemo(() => {
    if (!enrichedHierarchy) return { nodes: [], links: [], svgWidth: 0, svgHeight: 0 }
    
    const root = hierarchy(enrichedHierarchy)
    const treeLayout = tree().nodeSize([NODE_W + H_GAP, LEVEL_GAP + NODE_H])
    treeLayout(root)

    const descendants = root.descendants()
    const minX = Math.min(...descendants.map((n) => n.x))
    const maxX = Math.max(...descendants.map((n) => n.x))
    const maxY = Math.max(...descendants.map((n) => n.y))

    // Shift so x=0 is leftmost node
    descendants.forEach((n) => { n.x -= minX })

    return {
      nodes: descendants,
      links: root.links(),
      svgWidth: maxX - minX + NODE_W + 40,
      svgHeight: maxY + NODE_H + 60,
    }
  }, [enrichedHierarchy])

  if (!enrichedHierarchy) {
    return (
      <div style={{ display: 'flex', width: '100%', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'rgba(27,31,39,0.55)', fontFamily: "'DM Mono', monospace" }}>Loading hierarchy...</span>
      </div>
    )
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflowX: 'auto', overflowY: 'auto' }}>
      {/* Legend */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          display: 'flex',
          gap: 12,
          zIndex: 10,
        }}
      >
        {Object.entries(STATUS_COLORS).map(([status, colors]) => (
          <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: 3,
                border: `1.5px solid ${colors.border}`,
                background: colors.bg,
              }}
            />
            <span style={{ color: '#727a86', fontSize: 10, fontFamily: "'DM Mono', monospace", textTransform: 'capitalize' }}>
              {status}
            </span>
          </div>
        ))}
      </div>

      <svg
        viewBox={`0 0 ${svgWidth + 40} ${svgHeight + 40}`}
        width="100%"
        height={svgHeight + 40}
        preserveAspectRatio="xMidYMin meet"
        style={{ display: 'block', marginTop: 40, maxWidth: '100%' }}
      >
        {/* Defs for attack path arrow marker + dashMove animation */}
        <defs>
          <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
            <path d="M0,0 L0,8 L8,4 Z" fill="#E03C3C" opacity="0.8" />
          </marker>
          <style>{`
            @keyframes dashMove {
              to { stroke-dashoffset: -20; }
            }
            .attack-path {
              stroke-dasharray: 8 4;
              animation: dashMove 0.5s linear infinite;
            }
            .attacking-border {
              stroke-dasharray: 6 3;
              animation: dashMove 0.4s linear infinite;
            }
            .node-group:hover rect { filter: brightness(1.15); }
            @keyframes slideInRight {
              from { transform: translateX(100%); }
              to   { transform: translateX(0); }
            }
          `}</style>
        </defs>

        <g transform="translate(20, 20)">
          {/* Connector lines */}
          {links.map((link, i) => (
            <path
              key={i}
              d={`M${link.source.x + NODE_W / 2},${link.source.y + NODE_H}
                  C${link.source.x + NODE_W / 2},${(link.source.y + link.target.y) / 2 + NODE_H / 2}
                   ${link.target.x + NODE_W / 2},${(link.source.y + link.target.y) / 2 + NODE_H / 2}
                   ${link.target.x + NODE_W / 2},${link.target.y}`}
              fill="none"
              stroke="rgba(17,20,26,0.12)"
              strokeWidth={1}
            />
          ))}

          {/* Attack paths — animated dashed red arrows */}
          {attackPaths.map((ap, i) => {
            if (!ap.path || ap.path.length < 2) return null
            const pathNodes = ap.path
              .map((pn) => nodes.find((n) => n.data.id === pn.id))
              .filter(Boolean)

            return pathNodes.slice(0, -1).map((n, j) => {
              const next = pathNodes[j + 1]
              if (!next) return null
              return (
                <path
                  key={`${i}-${j}`}
                  className="attack-path"
                  d={`M${n.x + NODE_W / 2},${n.y}
                      L${next.x + NODE_W / 2},${next.y + NODE_H}`}
                  fill="none"
                  stroke="#E03C3C"
                  strokeWidth={2}
                  strokeOpacity={0.75}
                  markerEnd="url(#arrow-red)"
                />
              )
            })
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const d = node.data
            const colors = STATUS_COLORS[d.status] || STATUS_COLORS.normal
            const isAttacking = d.status === 'attacking'
            const isInfected = d.status === 'infected'
            // Configured-but-unobserved baseline host — dim the whole card so
            // it reads as distinct from hosts that actually appeared in
            // captured traffic (Error.md #9).
            const isConfiguredOnly = d.source === 'configured'

            return (
              <g
                key={d.id}
                className="node-group"
                transform={`translate(${node.x}, ${node.y})`}
                style={{ cursor: 'pointer', opacity: isConfiguredOnly ? 0.45 : 1 }}
                onClick={() => setSelectedNode(d)}
              >
                {/* Node card */}
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={8}
                  fill={colors.bg}
                  stroke={colors.border}
                  strokeWidth={isAttacking ? 1.5 : 0.75}
                  strokeDasharray={isConfiguredOnly ? '3,2' : undefined}
                  className={isAttacking ? 'attacking-border' : ''}
                />

                {/* Label */}
                <text
                  x={NODE_W / 2}
                  y={NODE_H / 2 - 7}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={12}
                  fontWeight={600}
                  fontFamily="'DM Mono', monospace"
                  fill={colors.text}
                >
                  {d.label}
                </text>

                {/* Sublabel */}
                <text
                  x={NODE_W / 2}
                  y={NODE_H / 2 + 9}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={9}
                  fontFamily="'DM Mono', monospace"
                  fill="rgba(27,31,39,0.40)"
                >
                  {d.sublabel}
                </text>

                {/* Level badge — top left */}
                <rect x={2} y={2} width={24} height={13} rx={4} fill="rgba(79,110,247,0.15)" />
                <text x={14} y={8.5} textAnchor="middle" dominantBaseline="central" fontSize={8} fontFamily="'DM Mono', monospace" fill="#3b56d9" fontWeight={700}>
                  L{d.level}
                </text>

                {/* Status badges */}
                {(d.status === 'isolated' || d.status === 'blocked') && (
                  <>
                    <rect x={NODE_W - 52} y={3} width={48} height={13} rx={4} fill={colors.border} />
                    <text x={NODE_W - 28} y={9.5} textAnchor="middle" dominantBaseline="central" fontSize={8} fontFamily="'DM Mono', monospace" fill="#fff" fontWeight={700}>
                      {d.status === 'isolated' ? 'ISOLATED' : 'BLOCKED'}
                    </text>
                  </>
                )}

                {d.status === 'attacking' && (
                  <>
                    <rect x={NODE_W - 62} y={3} width={60} height={13} rx={4} fill="rgba(224,60,60,0.25)" />
                    <text x={NODE_W - 32} y={9.5} textAnchor="middle" dominantBaseline="central" fontSize={8} fontFamily="'DM Mono', monospace" fill="#E03C3C" fontWeight={700}>
                      ESCALATING
                    </text>
                  </>
                )}

                {/* Infected pulsing dot */}
                {isInfected && (
                  <circle cx={NODE_W - 8} cy={8} r={4} fill="#b7791f">
                    <animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite" />
                  </circle>
                )}
              </g>
            )
          })}
        </g>
      </svg>

      {/* Node inspector panel */}
      {selectedNode && (
        <NodeInspector
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  )
}
