// Landing page network scene. Plain three.js so the live story (r3f) and the
// frame export script render the exact same picture. Every value is a pure
// function of scroll progress: nothing here reads a clock.
import * as THREE from 'three'
import { heroSwing } from './framing'

export const PALETTE = {
  bone: '#EBE7DF',
  charcoal: '#2B2A28',
  crimson: '#B4132E',
}

export const HOST_COUNT = 10
export const ATTACKER = 1 // h2, 10.0.0.2: the node the demo DDoS script uses
export const CHAPTERS = 5

const RING = 3
const NODE_Y = 0.55
const HUB_Y = 0.7
const CHAIN_Z = 4.2
const CHAIN_Y = 0.3
const BLOCKS = 5
const ATTACK_PACKETS = 8

const sat = (x) => Math.min(1, Math.max(0, x))
const range = (x, a, b) => sat((x - a) / (b - a))
const ease = (t) => t * t * (3 - 2 * t)
const er = (x, a, b) => ease(range(x, a, b))
const lerp = (a, b, t) => a + (b - a) * t
const fract = (x) => x - Math.floor(x)
const tint = (a, b, t) => new THREE.Color(a).lerp(new THREE.Color(b), t)

const hostAngle = (i) => THREE.MathUtils.degToRad(35 + (i - ATTACKER) * 36)
const hostPos = (i, y = NODE_Y) =>
  new THREE.Vector3(Math.sin(hostAngle(i)) * RING, y, Math.cos(hostAngle(i)) * RING)

// ── Camera ──────────────────────────────────────────────────────────────
// T runs 0..1 across the cinematic, then 1..6 across the five chapters.
//            T    azimuth elev  dist   target
const CAM_KEYS = [
  [0.0, -0.25, 1.05, 11.5, 0.0, 0.2, 0.0],
  [1.0, 0.1, 0.5, 9.6, 0.0, 0.4, 0.0],
  [2.0, 0.24, 0.46, 9.2, 0.2, 0.4, 0.3],
  [2.6, 0.28, 0.45, 7.6, 1.1, 0.5, 1.7],
  [3.6, 0.36, 0.45, 7.3, 1.2, 0.45, 1.8],
  [4.5, 0.12, 0.58, 9.6, 0.0, 0.3, 1.6],
  [6.0, -0.3, 0.66, 10.6, 0.0, 0.3, 1.2],
]

function sampleKeys(T) {
  const keys = CAM_KEYS
  let k = 0
  while (k < keys.length - 2 && T > keys[k + 1][0]) k++
  const a = keys[k]
  const b = keys[k + 1]
  const t = er(T, a[0], b[0])
  return a.map((v, i) => lerp(v, b[i], t))
}

// The frame sequence is rendered at one reference aspect per orientation and
// drawn height-held (the full frame height always shows), centred. The live
// camera mirrors that by always holding its vertical field of view.
const REFERENCE = {
  landscape: { fov: 32, dist: 1 },
  portrait: { fov: 40, dist: 1.9 },
}

export function applyCamera(camera, { intro, story, aspect, side = true, centered = false }) {
  const portrait = aspect < 1
  const ref = portrait ? REFERENCE.portrait : REFERENCE.landscape
  const T = intro < 1 ? intro : 1 + story
  const [, az, el, dist, tx, ty, tz] = sampleKeys(T)

  camera.fov = ref.fov
  camera.aspect = aspect

  // Story-only adjustments fade in after the handoff, so frame 1 of the live
  // scene is identical to the last frame of the sequence.
  const storyW = er(T, 1, 1.25)
  let scale = ref.dist
  let ox = 0
  let oy = 0.13
  if (!portrait) {
    // Cinematic: the network is centred on the window, small and high so it
    // sits above the title and clear of the card, then comes forward as the
    // title leaves.
    const swing = heroSwing(T)
    scale = lerp(1.8, 1.05, swing)
    oy = lerp(0.2, 0.07, swing)
    if (side) {
      // Story: pull back and shift right so the scene clears the type column.
      const squeeze = 0.5 * sat((1.78 - aspect) / 0.6)
      scale = lerp(scale, 1.22 + squeeze, storyW)
      ox = lerp(ox, 0.2, storyW) - 0.04 * er(T, 5.2, 6)
      oy = lerp(oy, 0, storyW)
    } else {
      oy = lerp(oy, 0.12, storyW)
    }
  } else {
    oy = lerp(oy, 0.17, storyW)
  }
  // Standalone stills are framed loosely so nothing runs off the edge.
  const d = dist * scale * (centered ? 1.3 : 1)

  camera.position.set(
    tx + d * Math.sin(az) * Math.cos(el),
    ty + d * Math.sin(el),
    tz + d * Math.cos(az) * Math.cos(el),
  )
  camera.lookAt(tx, ty, tz)

  if (centered) {
    ox = 0
    oy = 0
  }
  const W = 1000 * aspect
  const H = 1000
  camera.setViewOffset(W, H, -ox * W, oy * H, W, H)
  camera.updateProjectionMatrix()
}

// ── Scene graph ─────────────────────────────────────────────────────────
export function createNetworkScene() {
  const group = new THREE.Group()
  const C = PALETTE

  group.add(new THREE.AmbientLight('#ffffff', Math.PI * 0.82))
  const sun = new THREE.DirectionalLight('#ffffff', Math.PI * 0.5)
  sun.position.set(4, 9, 6)
  group.add(sun)

  const flat = (color) => new THREE.MeshBasicMaterial({ color })
  const solid = (color) => new THREE.MeshLambertMaterial({ color, flatShading: true })

  // Ground marks
  const groundMat = flat(tint(C.bone, C.charcoal, 0.16))
  const ring = new THREE.Mesh(new THREE.RingGeometry(RING - 0.008, RING + 0.008, 96), groundMat)
  ring.rotation.x = -Math.PI / 2
  const outer = new THREE.Mesh(
    new THREE.RingGeometry(4.35, 4.36, 96),
    flat(tint(C.bone, C.charcoal, 0.09)),
  )
  outer.rotation.x = -Math.PI / 2
  group.add(ring, outer)

  // Switch
  const hub = new THREE.Mesh(new THREE.OctahedronGeometry(0.5, 0), solid(C.charcoal))
  hub.position.y = HUB_Y
  const hubShadow = new THREE.Mesh(
    new THREE.CircleGeometry(0.5, 24),
    flat(tint(C.bone, C.charcoal, 0.1)),
  )
  hubShadow.rotation.x = -Math.PI / 2
  hubShadow.position.y = 0.002
  group.add(hub, hubShadow)

  // Hosts, links, score bars
  const nodeGeo = new THREE.IcosahedronGeometry(0.26, 0)
  const discGeo = new THREE.CircleGeometry(0.3, 20)
  const rodGeo = new THREE.CylinderGeometry(0.009, 0.009, 1, 5)
  const linkMat = flat(tint(C.bone, C.charcoal, 0.62))
  const discMat = flat(tint(C.bone, C.charcoal, 0.1))
  const barMat = flat(tint(C.bone, C.charcoal, 0.8))
  const up = new THREE.Vector3(0, 1, 0)
  const hubPos = new THREE.Vector3(0, HUB_Y, 0)

  const hosts = []
  for (let i = 0; i < HOST_COUNT; i++) {
    const home = hostPos(i)
    const node = new THREE.Mesh(nodeGeo, solid(C.charcoal))
    node.rotation.set(i * 0.7, i * 1.3, 0)
    const disc = new THREE.Mesh(discGeo, discMat)
    disc.rotation.x = -Math.PI / 2
    disc.position.set(home.x, 0.002, home.z)

    // Link runs between the two surfaces, not the two centres.
    const dir = home.clone().sub(hubPos).normalize()
    const a = hubPos.clone().addScaledVector(dir, 0.42)
    const b = home.clone().addScaledVector(dir, -0.3)
    const quat = new THREE.Quaternion().setFromUnitVectors(up, dir)
    const inner = new THREE.Mesh(rodGeo, linkMat)
    const outerHalf = new THREE.Mesh(rodGeo, linkMat)
    inner.quaternion.copy(quat)
    outerHalf.quaternion.copy(quat)

    const bar = new THREE.Mesh(rodGeo, barMat)
    group.add(node, disc, inner, outerHalf, bar)
    hosts.push({ home, node, disc, a, b, inner, outerHalf, bar, score: 0.1 + fract(i * 0.37) * 0.22 })
  }

  const setSegment = (mesh, a, b, u0, u1) => {
    if (u1 - u0 < 0.002) {
      mesh.visible = false
      return
    }
    mesh.visible = true
    mesh.position.lerpVectors(a, b, (u0 + u1) / 2)
    mesh.scale.set(1, a.distanceTo(b) * (u1 - u0), 1)
  }

  // Packets
  const packetCount = HOST_COUNT * 2 + ATTACK_PACKETS
  const packets = new THREE.InstancedMesh(
    new THREE.OctahedronGeometry(0.055, 0),
    new THREE.MeshBasicMaterial({ color: '#ffffff' }),
    packetCount,
  )
  packets.frustumCulled = false
  const neutral = tint(C.bone, C.charcoal, 0.85)
  const crimson = new THREE.Color(C.crimson)
  // Lit faces brighten their base colour, so lit crimson starts a little darker.
  const litCrimson = crimson.clone().multiplyScalar(0.84)
  for (let k = 0; k < packetCount; k++) {
    const hostile = k >= HOST_COUNT * 2 || Math.floor(k / 2) === ATTACKER
    packets.setColorAt(k, hostile ? crimson : neutral)
  }
  group.add(packets)
  const dummy = new THREE.Object3D()

  // Attacker markers
  const crimsonMat = flat(C.crimson)
  const attacker = hosts[ATTACKER]
  const flagRing = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.014, 6, 64), crimsonMat)
  flagRing.rotation.x = -Math.PI / 2
  flagRing.position.set(attacker.home.x, 0.02, attacker.home.z)
  const pin = new THREE.Mesh(rodGeo, crimsonMat)
  const cage = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(0.92, 0.92, 0.92)),
    new THREE.LineBasicMaterial({ color: C.charcoal }),
  )
  group.add(flagRing, pin, cage)

  // Chain of blocks
  const blockGeo = new THREE.BoxGeometry(0.44, 0.44, 0.44)
  const blocks = []
  const blockLinks = []
  const slot = (k) => new THREE.Vector3(-1.9 + 0.95 * k, CHAIN_Y, CHAIN_Z)
  for (let k = 0; k < BLOCKS; k++) {
    const last = k === BLOCKS - 1
    const block = new THREE.Mesh(blockGeo, solid(last ? litCrimson : C.charcoal))
    block.position.copy(slot(k))
    group.add(block)
    blocks.push(block)
    if (k > 0) {
      const link = new THREE.Mesh(rodGeo, linkMat)
      link.rotation.z = Math.PI / 2
      group.add(link)
      blockLinks.push(link)
    }
  }
  const sideA = new THREE.Vector3()
  const sideB = new THREE.Vector3()
  const charcoal = new THREE.Color(C.charcoal)

  function update(intro, story) {
    const total = intro + story
    hub.rotation.y = total * 0.55

    const sever = er(story, 2.1, 2.7)
    const scored = er(story, 0.95, 1.4) * (1 - er(story, 2.0, 2.35))
    const flagged = er(story, 1.05, 1.5)
    // The attacker turns crimson during the cinematic's hold, while it is still
    // behind the hero's glass card, before the camera swings away.
    const ignite = er(intro, 0.62, 0.8)
    const packetsIn = er(intro, 0.58, 0.74)
    const flow = intro * 1.5 + story * 2.2

    hosts.forEach((h, i) => {
      const hostile = i === ATTACKER
      const rise = er(intro, 0.04 + 0.03 * i, 0.34 + 0.03 * i)
      const draw = er(intro, 0.34 + 0.025 * i, 0.56 + 0.025 * i)

      let scale = lerp(0.3, 1, rise)
      let y = lerp(0.12, NODE_Y, rise)
      if (hostile) {
        scale *= 1 + 0.25 * ignite + 0.3 * flagged - 0.4 * sever
        y -= 0.15 * sever
        h.node.material.color.copy(charcoal).lerp(litCrimson, ignite)
      }
      h.node.position.set(h.home.x, y, h.home.z)
      h.node.scale.setScalar(scale)
      h.disc.scale.setScalar(lerp(0.45, 1, rise))

      // Links draw outward from the switch; the attacker's is cut at the middle.
      const cut = hostile ? sever : 0
      setSegment(h.inner, h.a, h.b, 0, Math.min(draw, 0.5) * (1 - 0.8 * cut))
      setSegment(h.outerHalf, h.a, h.b, lerp(0.5, 1, cut), Math.max(draw, 0.5))

      // Per-node threat score, drawn as a bar above the node.
      const height = hostile ? 1.25 * flagged * (1 - er(story, 2.5, 2.9)) : h.score * scored
      const bar = hostile ? pin : h.bar
      if (hostile) h.bar.visible = false
      bar.visible = height > 0.01
      bar.position.set(h.home.x, y + 0.42 + height / 2, h.home.z)
      bar.scale.set(hostile ? 1.6 : 1.3, Math.max(height, 0.001), hostile ? 1.6 : 1.3)

      for (let j = 0; j < 2; j++) {
        const u = fract(flow * (0.5 + 0.11 * ((i * 3 + j) % 5)) + i * 0.173 + j * 0.5)
        const along = j === 0 ? u : 1 - u
        const size = packetsIn * draw * Math.sqrt(Math.sin(Math.PI * u)) * (1 - cut)
        dummy.position.lerpVectors(h.a, h.b, along)
        dummy.scale.setScalar(Math.max(size, 0.0001))
        dummy.updateMatrix()
        packets.setMatrixAt(i * 2 + j, dummy.matrix)
      }
    })

    // The flood: extra crimson packets streaming from the attacker to the switch.
    for (let k = 0; k < ATTACK_PACKETS; k++) {
      const on = er(story, 0.12 + 0.08 * k, 0.3 + 0.08 * k) * (1 - sever)
      const u = fract(flow * 1.35 + k / ATTACK_PACKETS)
      dummy.position.lerpVectors(attacker.a, attacker.b, 1 - u)
      dummy.scale.setScalar(Math.max(on * Math.sqrt(Math.sin(Math.PI * u)) * 1.15, 0.0001))
      dummy.updateMatrix()
      packets.setMatrixAt(HOST_COUNT * 2 + k, dummy.matrix)
    }
    packets.instanceMatrix.needsUpdate = true

    flagRing.scale.setScalar(Math.max(flagged, 0.0001))
    flagRing.visible = flagged > 0.001

    const caged = er(story, 2.4, 2.9)
    cage.visible = caged > 0.001
    cage.position.copy(attacker.node.position)
    cage.scale.setScalar(Math.max(caged, 0.0001))
    cage.rotation.y = hostAngle(ATTACKER)

    // Record: older blocks surface, then the incident travels out and seals on.
    blocks.forEach((block, k) => {
      const last = k === BLOCKS - 1
      if (!last) {
        const s = er(story, 3.0 + 0.07 * k, 3.3 + 0.07 * k)
        block.scale.setScalar(Math.max(s, 0.0001))
        block.visible = s > 0.001
        return
      }
      const travel = er(story, 3.3, 3.82)
      const s = er(story, 3.22, 3.4) * lerp(0.45, 1, travel)
      block.position.lerpVectors(attacker.node.position, slot(k), travel)
      block.position.y += Math.sin(Math.PI * travel) * 1.1
      block.rotation.y = (1 - travel) * 1.4
      block.scale.setScalar(Math.max(s, 0.0001))
      block.visible = s > 0.001
    })
    blockLinks.forEach((link, k) => {
      const last = k === BLOCKS - 2
      const drawn = last ? er(story, 3.8, 3.96) : er(story, 3.12 + 0.07 * k, 3.36 + 0.07 * k)
      sideA.copy(slot(k)).x += 0.22
      sideB.copy(slot(k + 1)).x -= 0.22
      setSegment(link, sideA, sideB, 0, drawn)
    })
  }

  // Draws everything once, visible and unculled, so the GPU has built every
  // shader before the scroll needs it, then restores the real state. Compiling
  // alone is not enough: the driver finishes the job on the first draw call.
  function warm(renderer, camera, root) {
    const culled = new Map()
    group.traverse((o) => {
      culled.set(o, o.frustumCulled)
      o.frustumCulled = false
      o.visible = true
    })
    renderer.compile(group, camera, root)
    renderer.render(root, camera)
    culled.forEach((value, o) => {
      o.frustumCulled = value
    })
    update(0, 0)
  }

  function dispose() {
    group.traverse((o) => {
      o.geometry?.dispose()
      o.material?.dispose()
    })
  }

  update(0, 0)
  return { group, update, warm, dispose }
}
