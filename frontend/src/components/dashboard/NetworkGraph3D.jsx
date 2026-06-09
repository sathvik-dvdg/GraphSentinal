// [Windows] GraphSentinel — Susheep
import { useRef, useCallback, useEffect, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'
import { STATUS_COLORS, ATTACK_COLORS } from '../../constants/theme'

export default function NetworkGraph3D({ graphData, healingNodeId, onNodeClick }) {
  const fgRef = useRef()
  const [animatedNodeId, setAnimatedNodeId] = useState(null)

  useEffect(() => {
    if (healingNodeId) {
      setAnimatedNodeId(healingNodeId)
      const t = setTimeout(() => setAnimatedNodeId(null), 3000)
      return () => clearTimeout(t)
    }
  }, [healingNodeId])

  // Auto-rotate camera slowly
  useEffect(() => {
    let angle = 0
    const timer = setInterval(() => {
      if (fgRef.current) {
        angle += 0.003
        fgRef.current.cameraPosition({
          x: 200 * Math.sin(angle),
          z: 200 * Math.cos(angle),
        })
      }
    }, 50)
    return () => clearInterval(timer)
  }, [])

  const nodeThreeObject = useCallback(
    (node) => {
      const group = new THREE.Group()
      const isHealing = node.id === animatedNodeId
      const isMalicious = node.status === 'malicious'
      const isBlocked = node.status === 'blocked'
      const isSuspicious = node.status === 'suspicious'

      // Main sphere
      const radius = isMalicious ? 7 : isBlocked ? 6 : isSuspicious ? 5 : 4
      const geo = new THREE.SphereGeometry(radius, 20, 20)
      const mat = new THREE.MeshPhongMaterial({
        color: new THREE.Color(STATUS_COLORS[node.status] || '#ffffff'),
        emissive: new THREE.Color(isMalicious ? '#ff1111' : '#000000'),
        emissiveIntensity: isMalicious ? 0.7 : 0,
        transparent: isBlocked,
        opacity: isBlocked ? 0.8 : 1,
        shininess: 100,
      })
      group.add(new THREE.Mesh(geo, mat))

      // Suspicious ring
      if (isSuspicious) {
        const ringGeo = new THREE.TorusGeometry(8, 0.5, 8, 32)
        const ringMat = new THREE.MeshBasicMaterial({
          color: '#ffaa00',
          transparent: true,
          opacity: 0.6,
        })
        group.add(new THREE.Mesh(ringGeo, ringMat))
      }

      // Blocked cage
      if (isBlocked) {
        const cageGeo = new THREE.WireframeGeometry(new THREE.SphereGeometry(12, 8, 8))
        const cageMat = new THREE.LineBasicMaterial({
          color: '#0066ff',
          transparent: true,
          opacity: 0.5,
        })
        group.add(new THREE.LineSegments(cageGeo, cageMat))
      }

      // Malicious point light
      if (isMalicious) {
        const light = new THREE.PointLight('#ff4444', 0.8, 30)
        group.add(light)
      }

      // Healing pulse
      if (isHealing) {
        const pulseGeo = new THREE.SphereGeometry(15, 16, 16)
        const pulseMat = new THREE.MeshBasicMaterial({
          color: '#0066ff',
          transparent: true,
          opacity: 0.3,
          wireframe: true,
        })
        group.add(new THREE.Mesh(pulseGeo, pulseMat))
      }

      // IP label sprite
      const canvas = document.createElement('canvas')
      canvas.width = 256
      canvas.height = 48
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = '#ffffff'
      ctx.font = '20px monospace'
      ctx.fillText(node.label || node.id, 8, 32)
      const tex = new THREE.CanvasTexture(canvas)
      const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true }))
      spr.scale.set(28, 7, 1)
      spr.position.set(0, radius + 10, 0)
      group.add(spr)

      // Threat score badge
      if (node.threat_score >= 0.5) {
        const badgeCanvas = document.createElement('canvas')
        badgeCanvas.width = 128
        badgeCanvas.height = 32
        const bctx = badgeCanvas.getContext('2d')
        bctx.fillStyle = node.threat_score >= 0.75 ? '#ff4444' : '#ffaa00'
        bctx.fillRect(0, 0, 128, 32)
        bctx.fillStyle = '#ffffff'
        bctx.font = 'bold 20px monospace'
        bctx.fillText(`${(node.threat_score * 100).toFixed(0)}%`, 10, 24)
        const badgeTex = new THREE.CanvasTexture(badgeCanvas)
        const badge = new THREE.Sprite(new THREE.SpriteMaterial({ map: badgeTex }))
        badge.scale.set(18, 5, 1)
        badge.position.set(0, -(radius + 8), 0)
        group.add(badge)
      }

      return group
    },
    [animatedNodeId]
  )

  const getLinkColor = useCallback(
    (link) => ATTACK_COLORS[link.attack_type] || ATTACK_COLORS.null,
    []
  )
  const getLinkWidth = useCallback(
    (link) => (link.value > 0.75 ? 3 : link.value > 0.5 ? 2 : 1),
    []
  )
  const getParticles = useCallback(
    (link) => (link.value > 0.75 ? 6 : link.value > 0.5 ? 3 : 1),
    []
  )
  const getParticleW = useCallback((link) => (link.value > 0.75 ? 3 : 2), [])

  return (
    <div className="w-full h-full bg-gs-bg">
      <ForceGraph3D
        ref={fgRef}
        graphData={graphData}
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        linkColor={getLinkColor}
        linkWidth={getLinkWidth}
        linkDirectionalParticles={getParticles}
        linkDirectionalParticleWidth={getParticleW}
        linkDirectionalParticleSpeed={0.007}
        linkDirectionalParticleColor={getLinkColor}
        backgroundColor="#0a0e1a"
        enableNodeDrag={true}
        enableNavigationControls={true}
        showNavInfo={false}
        onNodeClick={(node) => {
          if (onNodeClick) onNodeClick(node)
          const d = 80
          const { x = 0, y = 0, z = 0 } = node
          fgRef.current?.cameraPosition(
            { x: x + d, y: y + d, z: z + d },
            { x, y, z },
            1000
          )
        }}
        nodeLabel={(node) =>
          `<div style="background:#1a2035;border:1px solid #334466;padding:4px 8px;
                       font-family:monospace;font-size:11px;color:#e2e8f0;border-radius:4px">
            <b>${node.label}</b> (${node.id})<br/>
            Status: <span style="color:${STATUS_COLORS[node.status]}">${node.status.toUpperCase()}</span><br/>
            Threat: ${(node.threat_score * 100).toFixed(1)}% | Conns: ${node.connections}
          </div>`
        }
      />
    </div>
  )
}
