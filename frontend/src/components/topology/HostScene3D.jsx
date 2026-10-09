// [Windows] GraphSentinel
// HostScene3D -- the 3D view of Network Topology. Hosts stand on a tilted floor
// around switch s1; the controller floats above it. Depth comes from the floor,
// the stems and the size of each marker, while labels stay flat and upright so
// they read at any angle. Only hosts that are not healthy carry a name tag, so
// the ones that matter are never hidden behind the rest. See utils/scene3d.js
// for the layout; this draws it.
import { useEffect, useMemo, useRef, useState } from 'react'
import { RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react'
import Button from '../ui/Button'
import { GS } from '../../constants/colors'
import { HOST_STATES } from '../../utils/hostState'
import { SCENE, layoutHosts, turn } from '../../utils/scene3d'

const LABEL_W = 132
const RING_STEP = 36

const EDGE = {
  healthy: { color: GS.rail, style: 'solid', width: 2 },
  watching: { color: GS.warn, style: 'solid', width: 2 },
  contained: { color: GS.danger, style: 'dashed', width: 2 },
  threat: { color: GS.danger, style: 'solid', width: 3 },
}

const abs = (left, top, extra) => ({ position: 'absolute', left, top, ...extra })

export default function HostScene3D({ hosts, selectedId, onSelect }) {
  const [rotation, setRotation] = useState(0)
  const [labelAll, setLabelAll] = useState(false)
  const frameRef = useRef(null)
  const [scale, setScale] = useState(1)

  // The scene is drawn at one size and scaled to the width it is given.
  useEffect(() => {
    const el = frameRef.current
    if (!el) return undefined
    const fit = () => setScale(Math.min(1, el.clientWidth / SCENE.w))
    fit()
    const obs = new ResizeObserver(fit)
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const placed = useMemo(() => layoutHosts(hosts, rotation), [hosts, rotation])
  const back = placed.filter((p) => p.back)
  const front = placed.filter((p) => !p.back)

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, padding: '10px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
        <Button size="sm" onClick={() => setRotation((r) => turn(r, -RING_STEP))}>
          <ChevronLeft size={14} aria-hidden="true" /> Rotate
        </Button>
        <Button size="sm" onClick={() => setRotation((r) => turn(r, RING_STEP))}>
          Rotate <ChevronRight size={14} aria-hidden="true" />
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setRotation(0)} disabled={rotation === 0}>
          <RotateCcw size={13} aria-hidden="true" /> Reset view
        </Button>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minHeight: 36, padding: '0 6px', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
          <input type="checkbox" checked={labelAll} onChange={(e) => setLabelAll(e.target.checked)} style={{ width: 16, height: 16 }} />
          Label every host
        </label>
      </div>

      <div ref={frameRef} style={{ width: '100%', height: SCENE.h * scale, overflow: 'hidden' }}>
        <div style={{ position: 'relative', width: SCENE.w, height: SCENE.h, margin: '0 auto', transform: `scale(${scale})`, transformOrigin: 'top left', ...(scale < 1 ? { margin: 0 } : {}) }}>
          <Floor />

          {/* controller, floating above the switch */}
          <div style={abs(SCENE.cx - 1, 126, { width: 0, height: SCENE.cy - SCENE.stem - 126 - 20, borderLeft: `2px dotted ${GS.textMuted}` })} />
          <div style={abs(SCENE.cx - 16, 94, { width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 8, background: GS.surfaceLift, border: `2px solid ${GS.text}`, fontSize: 12, fontWeight: 700 })}>c0</div>
          <div style={abs(SCENE.cx + 26, 94, { height: 32, display: 'flex', alignItems: 'center', fontSize: 12, color: GS.textMuted })}>controller</div>

          {/* links first, so every marker sits above them */}
          {placed.map((p) => {
            const e = EDGE[p.host.state]
            return (
              <div
                key={`edge-${p.host.id}`}
                aria-hidden="true"
                style={abs(SCENE.cx, SCENE.cy - SCENE.stem, {
                  width: p.link.length, height: 0, transformOrigin: '0 0', transform: `rotate(${p.link.angle}deg)`,
                  borderTop: `${e.width}px ${e.style} ${e.color}`,
                })}
              />
            )
          })}

          {back.map((p) => <Node key={p.host.id} p={p} selected={selectedId === p.host.id} labelAll={labelAll} onSelect={onSelect} />)}

          {/* the switch */}
          <div style={abs(SCENE.cx - 14, SCENE.cy - 5, { width: 28, height: 10, borderRadius: '50%', background: 'rgba(43,42,40,0.2)' })} />
          <div style={abs(SCENE.cx - 1, SCENE.cy - SCENE.stem, { width: 2, height: SCENE.stem, background: 'rgba(43,42,40,0.3)' })} />
          <div style={abs(SCENE.cx - 20, SCENE.cy - SCENE.stem - 20, { width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, background: GS.text, color: GS.surface, fontSize: 14, fontWeight: 700 })}>s1</div>
          <div style={abs(SCENE.cx + 28, SCENE.cy - SCENE.stem - 10, { fontSize: 12, color: GS.textMuted })}>switch</div>

          {front.map((p) => <Node key={p.host.id} p={p} selected={selectedId === p.host.id} labelAll={labelAll} onSelect={onSelect} />)}
        </div>
      </div>

      <Key />
    </div>
  )
}

function Floor() {
  const ring = (w, h, style) => abs(SCENE.cx - w / 2, SCENE.cy - h / 2, { width: w, height: h, boxSizing: 'border-box', borderRadius: '50%', ...style })
  return (
    <>
      <div aria-hidden="true" style={ring(720, 300, { background: 'rgba(43,42,40,0.045)', border: '1px solid rgba(43,42,40,0.14)' })} />
      <div aria-hidden="true" style={ring(600, 240, { border: '1px dashed rgba(43,42,40,0.2)' })} />
      <div aria-hidden="true" style={ring(330, 132, { border: '1px dashed rgba(43,42,40,0.14)' })} />
    </>
  )
}

// A shape for each state, so no state rests on colour alone: circle, diamond,
// square, triangle. The fill and edge come from the shared .gs-state variables.
function markShape(state, size) {
  const base = { display: 'block', boxSizing: 'border-box', width: size, height: size, background: 'var(--st-fill)', border: 'var(--st-edge)' }
  if (state === 'healthy') return { ...base, borderRadius: '50%' }
  if (state === 'watching') return { ...base, borderRadius: 3, transform: 'rotate(45deg)' }
  if (state === 'threat') return { display: 'block', width: size + 4, height: size + 4, background: GS.danger, clipPath: 'polygon(50% 0, 100% 100%, 0 100%)' }
  return { ...base, borderRadius: 4 }
}

function Node({ p, selected, labelAll, onSelect }) {
  const { host, x, y, mx, my, size, right } = p
  const meta = HOST_STATES[host.state]
  const tagged = host.state !== 'healthy' || labelAll || selected
  const ring = selected ? { boxShadow: `0 0 0 3px ${GS.surface}, 0 0 0 5px ${GS.text}` } : null

  const labelLeft = right ? mx + Math.round(size / 2) + 14 : mx - Math.round(size / 2) - 14 - LABEL_W
  const tagLeft = right ? mx + Math.round(size / 2) + 8 : mx - Math.round(size / 2) - 8 - 36

  return (
    <div className="gs-state" data-state={host.state} style={abs(0, 0, { width: 0, height: 0 })}>
      <div aria-hidden="true" style={abs(x - 14, y - 5, { width: 28, height: 10, borderRadius: '50%', background: 'rgba(43,42,40,0.16)' })} />
      <div aria-hidden="true" style={abs(mx - 1, my, { width: 2, height: SCENE.stem, background: 'rgba(43,42,40,0.22)' })} />
      <button
        type="button"
        aria-label={`Select ${host.label}, ${meta.label}`}
        aria-pressed={selected}
        onClick={() => onSelect(host.id)}
        style={abs(mx - 22, my - 22, { width: 44, height: 44, padding: 0, border: 0, background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' })}
      >
        <span style={{ ...markShape(host.state, size), ...ring }} />
      </button>

      {tagged ? (
        <button
          type="button"
          tabIndex={-1}
          aria-hidden="true"
          onClick={() => onSelect(host.id)}
          style={abs(labelLeft, my - 18, {
            width: LABEL_W, boxSizing: 'border-box', padding: '5px 10px', textAlign: 'left', borderRadius: 8, cursor: 'pointer',
            color: GS.text, font: "12px/16px var(--font-sans)",
            background: host.state === 'healthy' ? GS.surfaceLift : 'var(--st-fill)',
            border: host.state === 'healthy' ? '1px solid rgba(43,42,40,0.25)' : 'var(--st-edge)',
            ...ring,
          })}
        >
          <b>{host.label}</b>
          <br />
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.04em', color: 'var(--st-fg)' }}>{meta.label}</span>
        </button>
      ) : (
        <div aria-hidden="true" style={abs(tagLeft, my - 8, { width: 36, textAlign: right ? 'left' : 'right', fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: '16px', color: GS.textBody })}>
          {host.label}
        </div>
      )}
    </div>
  )
}

function Key() {
  const swatch = { display: 'inline-block', width: 14, height: 14, boxSizing: 'border-box' }
  return (
    <ul style={{ listStyle: 'none', display: 'flex', flexWrap: 'wrap', gap: '8px 20px', padding: '12px 20px', borderTop: '1px solid var(--border-subtle)', fontSize: 13, color: GS.textBody }} aria-label="3D view key">
      <li style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span className="gs-state" data-state="healthy" style={{ ...swatch, borderRadius: '50%', border: `2px solid ${GS.success}` }} />Healthy (circle)</li>
      <li style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}><span style={{ ...swatch, width: 12, height: 12, borderRadius: 2, transform: 'rotate(45deg)', background: GS.warnWash, border: `2px solid ${GS.warn}` }} />Watching (diamond)</li>
      <li style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span className="gs-state" data-state="contained" style={{ ...swatch, borderRadius: 3, background: 'var(--st-fill)', border: '2px dashed var(--st-fg)' }} />Isolated (square)</li>
      <li style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span style={{ ...swatch, background: GS.danger, clipPath: 'polygon(50% 0, 100% 100%, 0 100%)' }} />Active threat (triangle)</li>
      <li style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <svg width="28" height="8" viewBox="0 0 28 8" aria-hidden="true"><path d="M0 4H28" stroke={GS.danger} strokeWidth="2" strokeDasharray="5 4" fill="none" /></svg>
        Traffic cut at s1
      </li>
    </ul>
  )
}
