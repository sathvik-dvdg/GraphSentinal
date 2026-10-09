import { useEffect, useRef } from 'react'
import { FRAME_COUNT, frameUrl } from './content'
import { GS } from '../../constants/colors'

const CONCURRENCY = 6
const BONE = GS.landingBone

// Coarse-to-fine load order: a fast scrub always has a nearby frame to hold on.
function loadOrder(count, first) {
  const order = [first, 0, count - 1]
  for (let stride = 16; stride >= 1; stride /= 2) {
    for (let i = 0; i < count; i += stride) order.push(i)
  }
  return [...new Set(order)]
}

function nearestLoaded(frames, target) {
  for (let d = 0; d < frames.length; d++) {
    if (frames[target - d]) return target - d
    if (frames[target + d]) return target + d
  }
  return -1
}

// Scroll-scrubbed image sequence on a single canvas.
// `progress` is a MotionValue in 0..1; `set` picks the desktop or mobile frames.
export default function SequenceCanvas({ progress, set, className }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    // Opaque: the frames cover the canvas, so it never needs to blend with the page.
    const ctx = canvas.getContext('2d', { alpha: false })
    const frames = new Array(FRAME_COUNT).fill(null)
    const target = () => Math.round(progress.get() * (FRAME_COUNT - 1))
    let cancelled = false
    let raf = 0
    let drawn = -1
    let drawnX = 0
    let dirty = true
    let sourceHeight = 0

    const draw = () => {
      raf = 0
      const index = nearestLoaded(frames, target())
      if (index < 0) return
      const img = frames[index]
      // Height-held and centred: the whole frame height always shows. A wider
      // canvas gets bone either side (the frame's own ground colour), a
      // narrower one crops the sides.
      const scale = canvas.height / img.naturalHeight
      const w = img.naturalWidth * scale
      const x = Math.round((canvas.width - w) / 2)
      if (index === drawn && x === drawnX && !dirty) return
      if (x > 0) {
        ctx.fillStyle = BONE
        ctx.fillRect(0, 0, canvas.width, canvas.height)
      }
      ctx.drawImage(img, x, 0, w, canvas.height)
      drawnX = x
      drawn = index
      dirty = false
    }
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(draw)
    }

    const resize = () => {
      // No more backing pixels than the frames have: drawing a frame into a
      // larger buffer costs fill and upload time and adds no detail.
      const detail = sourceHeight ? Math.max(1, sourceHeight / canvas.clientHeight) : 2
      const dpr = Math.min(window.devicePixelRatio || 1, 2, detail)
      const w = Math.round(canvas.clientWidth * dpr)
      const h = Math.round(canvas.clientHeight * dpr)
      if (!w || !h || (w === canvas.width && h === canvas.height)) return
      canvas.width = w
      canvas.height = h
      dirty = true
      schedule()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(canvas)
    resize()

    const queue = loadOrder(FRAME_COUNT, target())
    const next = (after) => {
      if (cancelled || !queue.length) return
      const index = queue.shift()
      const img = new Image()
      img.decoding = 'async'
      img.onload = () => {
        if (cancelled) return
        frames[index] = img
        if (!sourceHeight) {
          sourceHeight = img.naturalHeight
          resize()
        }
        schedule()
        ;(after || next)()
      }
      img.onerror = () => (after || next)()
      img.src = frameUrl(set, index)
    }
    // The first frame goes out alone so the hero paints before the rest compete
    // for bandwidth; then the remaining frames load a few at a time.
    next(() => {
      for (let i = 0; i < CONCURRENCY; i++) next()
    })

    const unsubscribe = progress.on('change', schedule)
    return () => {
      cancelled = true
      unsubscribe()
      observer.disconnect()
      cancelAnimationFrame(raf)
    }
  }, [progress, set])

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />
}
