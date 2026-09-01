// [Windows] GraphSentinel — Susheep
// § 4.3 Fix: Geometry/material objects cached per status; label sprites cached by label text
// No new THREE allocations per render cycle
import { useRef, useCallback, useEffect, useState, useMemo } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'
import { STATUS_COLORS, ATTACK_COLORS } from '../../constants/theme'

export default function NetworkGraph3D({ graphData, healingNodeId, onNodeClick }) {
  const fgRef = useRef()
  const containerRef = useRef()
  const [animatedNodeId, setAnimatedNodeId] = useState(null)
  // react-force-graph-3d's own container auto-sizing was measuring the full
  // viewport instead of this panel (visible as a tiny, off-center scene
  // clipped inside the actual panel bounds) — track the real container size
  // ourselves and pass it explicitly rather than relying on that detection.
  const [size, setSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const update = () => setSize({ width: el.clientWidth, height: el.clientHeight })
    update()
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // ── Cached per-status objects — built ONCE on mount using useMemo ──
  const statusObjects = useMemo(() => {
    const statuses = ['normal', 'suspicious', 'malicious', 'blocked']
    const objects = {}

    for (const status of statuses) {
      const radius =
        status === 'malicious' ? 7 :
        status === 'blocked'   ? 6 :
        status === 'suspicious'? 5 : 4

      // Solid faceted nodes with a darker edge outline — reads clearly on the
      // white canvas (a faint wireframe washed out against it).
      const geo = new THREE.IcosahedronGeometry(radius, 0)
      const mat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(STATUS_COLORS[status] || '#9AA1AD'),
        wireframe: false,
        transparent: true,
        opacity: status === 'malicious' ? 1 : status === 'normal' ? 0.9 : 0.95,
      })
      const edgeMat = new THREE.LineBasicMaterial({
        color: new THREE.Color(status === 'normal' ? '#5A616E' : STATUS_COLORS[status] || '#5A616E'),
        transparent: true,
        opacity: 0.55,
      })
      const edgeGeo = new THREE.EdgesGeometry(geo)

      // Ring geometry for suspicious
      let ringGeo = null, ringMat = null
      if (status === 'suspicious') {
        ringGeo = new THREE.TorusGeometry(8, 0.2, 4, 16)
        ringMat = new THREE.MeshBasicMaterial({ color: '#b7791f', wireframe: true, transparent: true, opacity: 0.5 })
      }

      // Cage geometry for blocked
      let cageGeo = null, cageMat = null
      if (status === 'blocked') {
        cageGeo = new THREE.BoxGeometry(14, 14, 14)
        cageMat = new THREE.LineBasicMaterial({ color: '#5E5CE6', transparent: true, opacity: 0.4 })
      }

      objects[status] = { geo, mat, radius, ringGeo, ringMat, cageGeo, cageMat, edgeGeo, edgeMat }
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
    ctx.fillStyle = '#1b1f27' // updated color from E8EDF5
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

  // The scene is intentionally static: it used to slowly auto-orbit, which
  // drifted the star off-centre and made it hard to point at a specific node
  // while explaining the topology. Users can still orbit by dragging.

  // ── nodeThreeObject — uses cached objects, no per-frame allocation ──
  const nodeThreeObject = useCallback(
    (node) => {
      const status = node.status || 'normal'
      const cached = statusObjects[status] || statusObjects.normal
      const isHealing = node.id === animatedNodeId

      const group = new THREE.Group()

      // ── Infrastructure nodes (configured star from base_topology.py) ──
      // The OVS switch (s1) and controller (c0) aren't hosts — draw them as
      // distinct solid shapes so the star reads as a real network fabric.
      if (node.kind === 'switch' || node.kind === 'controller') {
        const isSwitch = node.kind === 'switch'
        const infraColor = isSwitch ? '#3b56d9' : '#5A616E'
        const geo = isSwitch
          ? new THREE.BoxGeometry(12, 5, 12)
          : new THREE.OctahedronGeometry(5, 0)
        const mat = new THREE.MeshBasicMaterial({
          color: new THREE.Color(status === 'suspicious' ? '#E8922A' : infraColor),
          wireframe: false,
          transparent: true,
          opacity: 0.9,
        })
        group.add(new THREE.Mesh(geo, mat))
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({ color: '#1b1f27', transparent: true, opacity: 0.35 })
        )
        group.add(edges)
        const { sprite } = getLabelSprite(node.label || node.id, 8)
        const spr = sprite.clone()
        spr.position.set(0, 12, 0)
        group.add(spr)
        return group
      }

      // Main sphere — cloned from cached geometry/material (no new allocation)
      // for the common case. Configured-but-unobserved baseline hosts (no
      // traffic seen yet) get a dimmed material clone so they read as
      // visually distinct from hosts that actually appeared in captured
      // traffic (Error.md #9) — cloning only this material, not the shared
      // one, so it doesn't dim every other node of the same status.
      const mesh = new THREE.Mesh(cached.geo, cached.mat)
      if (node.source === 'configured') {
        mesh.material = cached.mat.clone()
        mesh.material.opacity = cached.mat.opacity * 0.5
      }
      group.add(mesh)
      if (cached.edgeGeo) group.add(new THREE.LineSegments(cached.edgeGeo, cached.edgeMat))

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
          color: '#3b56d9',
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
          bctx.fillStyle = node.threat_score >= 0.75 ? '#E03C3C' : '#b7791f'
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
    (link) => (link.kind === 'infra' ? 0 : link.value > 0.75 ? 6 : link.value > 0.5 ? 3 : 1),
    []
  )
  const getParticleW = useCallback((link) => (link.value > 0.75 ? 3 : 2), [])

  return (
    <div ref={containerRef} className="w-full h-full bg-transparent">
      {size.width > 0 && size.height > 0 && (
      <ForceGraph3D
        ref={fgRef}
        width={size.width}
        height={size.height}
        graphData={graphData}
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        linkColor={getLinkColor}
        linkWidth={getLinkWidth}
        linkOpacity={0.9}
        linkDirectionalParticles={getParticles}
        linkDirectionalParticleWidth={getParticleW}
        linkDirectionalParticleSpeed={0.007}
        linkDirectionalParticleColor={getLinkColor}
        backgroundColor="rgba(0,0,0,0)"
        enableNodeDrag={true}
        enableNavigationControls={true}
        showNavInfo={false}
        cooldownTicks={100}
        d3AlphaDecay={0.05}
        d3VelocityDecay={0.4}
        onEngineTick={() => {
          if (fgRef.current) {
            fgRef.current.d3Force('charge').distanceMax(220)
          }
        }}
        onEngineStop={() => {
          fgRef.current?.zoomToFit(500, 45)
        }}
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
          `<div style="background:#ffffff;border:1px solid #e2e5ea;padding:6px 10px;
                       font-family:'DM Mono',monospace;font-size:11px;color:#1b1f27;border-radius:6px;line-height:1.6">
            <b style="color:#3b56d9">${node.label}</b> (${node.id})<br/>
            Status: <span style="color:${STATUS_COLORS[node.status]}">${node.status?.toUpperCase()}</span>
            ${node.status === 'malicious' ? ' ▲' : node.status === 'blocked' ? ' ⬡' : node.status === 'suspicious' ? ' ◆' : ' ●'}<br/>
            Threat: ${(node.threat_score * 100).toFixed(1)}% | Conns: ${node.connections}
            ${node.source ? `<br/><span style="color:${node.source === 'observed' ? '#12a672' : '#727a86'}">${node.source === 'observed' ? '◆ Observed traffic' : '○ Configured, no traffic yet'}</span>` : ''}
          </div>`
        }
      />
      )}
    </div>
  )
}
