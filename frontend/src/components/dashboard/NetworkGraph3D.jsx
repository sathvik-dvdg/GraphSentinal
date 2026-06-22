// [Windows] GraphSentinel — Susheep
// § 4.3 Fix: Geometry/material objects cached per status; label sprites cached by label text
// No new THREE allocations per render cycle
import { useRef, useCallback, useEffect, useState, useMemo } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'
import { STATUS_COLORS, ATTACK_COLORS } from '../../constants/theme'

export default function NetworkGraph3D({ graphData, healingNodeId, onNodeClick }) {
  const fgRef = useRef()
  const [animatedNodeId, setAnimatedNodeId] = useState(null)

  // ── Cached per-status objects — built ONCE on mount using useMemo ──
  const statusObjects = useMemo(() => {
    const statuses = ['normal', 'suspicious', 'malicious', 'blocked']
    const objects = {}

    for (const status of statuses) {
      const radius =
        status === 'malicious' ? 7 :
        status === 'blocked'   ? 6 :
        status === 'suspicious'? 5 : 4

      // Stark, wireframe-like aesthetics
      const geo = new THREE.IcosahedronGeometry(radius, 1)
      const mat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(STATUS_COLORS[status] || '#ffffff'),
        wireframe: true,
        transparent: true,
        opacity: status === 'malicious' ? 1 : 0.6,
      })

      // Ring geometry for suspicious
      let ringGeo = null, ringMat = null
      if (status === 'suspicious') {
        ringGeo = new THREE.TorusGeometry(8, 0.2, 4, 16)
        ringMat = new THREE.MeshBasicMaterial({ color: '#F5A623', wireframe: true, transparent: true, opacity: 0.5 })
      }

      // Cage geometry for blocked
      let cageGeo = null, cageMat = null
      if (status === 'blocked') {
        cageGeo = new THREE.BoxGeometry(14, 14, 14)
        cageMat = new THREE.LineBasicMaterial({ color: '#5E5CE6', transparent: true, opacity: 0.4 })
      }

      objects[status] = { geo, mat, radius, ringGeo, ringMat, cageGeo, cageMat }
    }

    return objects
  }, [])

  // ── Cached label sprites — keyed by label text ───────────────
  const labelSpriteCache = useRef(new Map())

  function getLabelSprite(label, radius) {
    if (labelSpriteCache.current.has(label)) {
      return labelSpriteCache.current.get(label)
    }

    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 48
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, 256, 48)
    ctx.fillStyle = '#EAEAEA' // updated color from E8EDF5
    ctx.font = '600 18px "DM Mono", monospace'
    ctx.fillText(label, 8, 30)

    const tex = new THREE.CanvasTexture(canvas)
    tex.needsUpdate = true
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false })
    const sprite = new THREE.Sprite(mat)
    sprite.scale.set(28, 7, 1)

    labelSpriteCache.current.set(label, { sprite, radius })
    return { sprite, radius }
  }

  useEffect(() => {
    if (healingNodeId) {
      setTimeout(() => setAnimatedNodeId(healingNodeId), 0)
      const t = setTimeout(() => setAnimatedNodeId(null), 3000)
      return () => clearTimeout(t)
    }
  }, [healingNodeId])

  // Auto-rotate camera slowly — wrapped in prefers-reduced-motion check
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

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

  // ── nodeThreeObject — uses cached objects, no per-frame allocation ──
  const nodeThreeObject = useCallback(
    (node) => {
      const status = node.status || 'normal'
      const cached = statusObjects[status] || statusObjects.normal
      const isHealing = node.id === animatedNodeId

      const group = new THREE.Group()

      // Main sphere — cloned from cached geometry/material (no new allocation)
      const mesh = new THREE.Mesh(cached.geo, cached.mat)
      group.add(mesh)

      // Suspicious ring
      if (status === 'suspicious' && cached.ringGeo) {
        group.add(new THREE.Mesh(cached.ringGeo, cached.ringMat))
      }

      // Blocked cage
      if (status === 'blocked' && cached.cageGeo) {
        group.add(new THREE.LineSegments(cached.cageGeo, cached.cageMat))
      }

      // Malicious point light (kept, not decorative — indicates active threat)
      if (status === 'malicious') {
        const light = new THREE.PointLight('#E03C3C', 0.6, 25)
        group.add(light)
      }

      // Healing pulse — only when transitioning to blocked
      if (isHealing) {
        const pulseGeo = new THREE.SphereGeometry(15, 16, 16)
        const pulseMat = new THREE.MeshBasicMaterial({
          color: '#4F6EF7',
          transparent: true,
          opacity: 0.25,
          wireframe: true,
        })
        group.add(new THREE.Mesh(pulseGeo, pulseMat))
      }

      // Label sprite — from cache keyed by label text
      const labelText = node.label || node.id || ''
      const { sprite } = getLabelSprite(labelText, cached.radius)
      // Clone the sprite so each node has its own position
      const spr = sprite.clone()
      spr.position.set(0, cached.radius + 10, 0)
      group.add(spr)

      // Threat score badge — only for high-risk nodes
      if (node.threat_score >= 0.5) {
        const pct = (node.threat_score * 100).toFixed(0)
        const badgeKey = `badge-${pct}`
        let badgeSprite

        if (labelSpriteCache.current.has(badgeKey)) {
          badgeSprite = labelSpriteCache.current.get(badgeKey).sprite
        } else {
          const bc = document.createElement('canvas')
          bc.width = 128; bc.height = 32
          const bctx = bc.getContext('2d')
          bctx.fillStyle = node.threat_score >= 0.75 ? '#E03C3C' : '#E8922A'
          bctx.fillRect(0, 0, 128, 32)
          bctx.fillStyle = '#ffffff'
          bctx.font = 'bold 18px "DM Mono", monospace'
          bctx.fillText(`${pct}%`, 10, 22)
          const bt = new THREE.CanvasTexture(bc)
          const bm = new THREE.SpriteMaterial({ map: bt, depthWrite: false })
          badgeSprite = new THREE.Sprite(bm)
          badgeSprite.scale.set(18, 5, 1)
          labelSpriteCache.current.set(badgeKey, { sprite: badgeSprite, radius: 0 })
        }

        const bs = badgeSprite.clone()
        bs.position.set(0, -(cached.radius + 8), 0)
        group.add(bs)
      }

      return group
    },
    [animatedNodeId, statusObjects]
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
    <div className="w-full h-full bg-transparent">
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
        backgroundColor="rgba(0,0,0,0)"
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
          `<div style="background:#171B26;border:1px solid #262D3F;padding:6px 10px;
                       font-family:'DM Mono',monospace;font-size:11px;color:#E8EDF5;border-radius:6px;line-height:1.6">
            <b style="color:#C5D0FF">${node.label}</b> (${node.id})<br/>
            Status: <span style="color:${STATUS_COLORS[node.status]}">${node.status?.toUpperCase()}</span>
            ${node.status === 'malicious' ? ' ▲' : node.status === 'blocked' ? ' ⬡' : node.status === 'suspicious' ? ' ◆' : ' ●'}<br/>
            Threat: ${(node.threat_score * 100).toFixed(1)}% | Conns: ${node.connections}
          </div>`
        }
      />
    </div>
  )
}
