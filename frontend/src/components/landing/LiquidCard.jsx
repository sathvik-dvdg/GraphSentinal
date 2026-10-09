import { useEffect, useRef } from 'react'

const TRACKING = '(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)'

// A "liquid" variant of the page's glass: sheerer, thicker at the rim, bending
// what is behind it, with a specular highlight that follows the cursor. `quiet`
// is for places where the card sits on flat ground with nothing behind it: no
// refraction and no tracking, just the fixed highlight the stylesheet provides.
export default function LiquidCard({ quiet = false, className = '', children }) {
  const ref = useRef(null)

  useEffect(() => {
    if (quiet) return undefined
    const el = ref.current
    const query = window.matchMedia(TRACKING)
    let raf = 0
    let attached = false
    let px = 0
    let py = 0

    // Position goes straight onto the element as custom properties, once per
    // animation frame; React never re-renders for a pointer move.
    const write = () => {
      raf = 0
      const box = el.getBoundingClientRect()
      el.style.setProperty('--ld-spec-x', `${(((px - box.left) / box.width) * 100).toFixed(1)}%`)
      el.style.setProperty('--ld-spec-y', `${(((py - box.top) / box.height) * 100).toFixed(1)}%`)
    }
    const onMove = (event) => {
      px = event.clientX
      py = event.clientY
      el.dataset.lit = 'true'
      if (!raf) raf = requestAnimationFrame(write)
    }
    const onLeave = () => {
      el.dataset.lit = 'false'
    }

    const detach = () => {
      if (!attached) return
      attached = false
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerleave', onLeave)
      cancelAnimationFrame(raf)
      raf = 0
      delete el.dataset.tracking
      delete el.dataset.lit
      el.style.removeProperty('--ld-spec-x')
      el.style.removeProperty('--ld-spec-y')
    }
    // Touch devices and reduced motion keep the fixed highlight: no listener.
    const sync = () => {
      if (!query.matches) return detach()
      if (attached) return undefined
      attached = true
      el.dataset.tracking = 'true'
      el.addEventListener('pointermove', onMove, { passive: true })
      el.addEventListener('pointerleave', onLeave, { passive: true })
      return undefined
    }

    sync()
    query.addEventListener('change', sync)
    return () => {
      query.removeEventListener('change', sync)
      detach()
    }
  }, [quiet])

  // Refraction: an SVG displacement map used as a backdrop filter, which only
  // Chromium renders. userAgentData is itself Chromium-only, so every other
  // browser keeps the stylesheet's blurred panel.
  useEffect(() => {
    if (quiet) return undefined
    const el = ref.current
    const brands = navigator.userAgentData?.brands || []
    if (!brands.some((entry) => entry.brand === 'Chromium')) return undefined
    el.dataset.refract = 'true'
    return () => {
      delete el.dataset.refract
    }
  }, [quiet])

  return (
    <div ref={ref} className={`ld-liquid${quiet ? ' ld-liquid--quiet' : ''} ${className}`.trim()}>
      {!quiet && (
        <svg className="ld-liquid__defs" width="0" height="0" aria-hidden="true">
          <filter
            id="ld-liquid-refract"
            x="0"
            y="0"
            width="1"
            height="1"
            colorInterpolationFilters="sRGB"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.006 0.012"
              numOctaves="2"
              seed="11"
              result="noise"
            />
            <feDisplacementMap
              in="SourceGraphic"
              in2="noise"
              scale="46"
              xChannelSelector="R"
              yChannelSelector="G"
              result="bent"
            />
            <feGaussianBlur in="bent" stdDeviation="3" />
          </filter>
        </svg>
      )}
      {children}
    </div>
  )
}
