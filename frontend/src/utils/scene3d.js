// [Windows] GraphSentinel
// utils/scene3d -- where each host stands in the 3D view of Network Topology.
// Free of React so it can be tested with `node --test`
// (frontend/tests/unit/scene3d.test.js).
//
// The view is a drawn projection, not a WebGL scene: hosts stand on a tilted
// floor around the switch, so a host nearer the bottom of the floor is nearer
// the viewer. Labels stay flat and upright, which is what keeps them readable
// at every angle. Rotating the ring is changing `rotation` (degrees).

export const SCENE = { w: 960, h: 560, cx: 480, cy: 340, rx: 300, ry: 120, stem: 46 }

/** One entry per host: its floor point (x, y), the point its marker sits at
 *  (mx, my: the floor point lifted by the stem), the link from the switch's
 *  marker to it, and which side of the switch it is on. Sorted from the back of
 *  the floor to the front, which is the order to paint them in. */
export function layoutHosts(hosts, rotation = 0, scene = SCENE) {
  const n = hosts.length
  if (n === 0) return []
  const step = 360 / n
  const out = hosts.map((host, k) => {
    // Start half a step round from the top so no host stands under the controller.
    const a = ((rotation - 90 + step / 2 + step * k) * Math.PI) / 180
    const x = Math.round(scene.cx + scene.rx * Math.cos(a))
    const y = Math.round(scene.cy + scene.ry * Math.sin(a))
    const depth = (Math.sin(a) + 1) / 2
    const mx = x
    const my = y - scene.stem
    const dx = mx - scene.cx
    const dy = my - (scene.cy - scene.stem)
    return {
      host,
      x, y, mx, my,
      depth,
      size: Math.round(20 + 8 * depth),
      right: Math.cos(a) >= 0,
      back: Math.sin(a) < 0,
      link: { length: Math.round(Math.hypot(dx, dy)), angle: Number(((Math.atan2(dy, dx) * 180) / Math.PI).toFixed(2)) },
    }
  })
  return out.sort((p, q) => p.y - q.y)
}

/** Keep a rotation in 0..359 whatever is added to it. */
export function turn(rotation, by) {
  return (((rotation + by) % 360) + 360) % 360
}
