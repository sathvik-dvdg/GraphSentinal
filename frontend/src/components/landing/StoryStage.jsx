import { Component, Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { motion, useMotionValueEvent, useScroll, useTransform } from 'framer-motion'
import SequenceCanvas from './SequenceCanvas'
import DashboardLink from './DashboardLink'
import LiquidCard from './LiquidCard'
import { CHAPTERS, CHAPTER_VH, INTRO_VH, PREMISE } from './content'
import { useSteppedWeight } from './typeScrub'

// three.js is the heaviest thing on the page; it loads after the hero paints.
const NetworkCanvas = lazy(() => import('./NetworkCanvas'))

const TRAVEL_VH = INTRO_VH + CHAPTER_VH * CHAPTERS.length
const sat = (x) => Math.min(1, Math.max(0, x))
const smooth = (t) => t * t * (3 - 2 * t)
const hideWhenClear = (opacity) => (opacity <= 0.01 ? 'hidden' : 'visible')

// Dev aid: open the page with ?live to see the live 3D scene through the
// opening cinematic instead of the exported frames. Both come from the same
// camera code, so this is how the cinematic's framing is tuned before the
// frames are re-exported. It is compiled out of production builds.
const LIVE_INTRO = import.meta.env.DEV && new URLSearchParams(window.location.search).has('live')

function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const list = window.matchMedia(query)
    const onChange = () => setMatches(list.matches)
    onChange()
    list.addEventListener('change', onChange)
    return () => list.removeEventListener('change', onChange)
  }, [query])
  return matches
}

// If WebGL is unavailable the last sequence frame stays up and the copy still reads.
class SceneBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? null : this.props.children
  }
}

function Hero({ intro }) {
  // The hero title is the largest type on the page, so each new weight is the
  // most expensive one to rasterise: it steps more coarsely than the rest.
  const weight = useSteppedWeight(intro, [0, 0.8], [240, 640], 40)
  const tracking = useTransform(intro, [0, 0.8], ['0.02em', '-0.045em'])
  const opacity = useTransform(intro, [0.8, 0.96], [1, 0])
  const y = useTransform(intro, [0.8, 0.96], ['0%', '-8%'])
  const visibility = useTransform(opacity, hideWhenClear)

  return (
    // The fade is handed down as a custom property and applied to each child
    // (see .ld-hero in landing.css). Opacity on this container would cut the
    // glass card and button off from the canvas behind them mid-fade.
    <motion.div className="ld-hero" style={{ '--ld-hero-fade': opacity, y, visibility }}>
      <motion.h1 className="ld-hero__title" style={{ fontWeight: weight, letterSpacing: tracking }}>
        GraphSentinel
      </motion.h1>
      <div className="ld-hero__row">
        <LiquidCard className="ld-hero__card">
          <p className="ld-hero__premise">{PREMISE}</p>
        </LiquidCard>
        <DashboardLink id="hero-cta-dashboard" />
      </div>
    </motion.div>
  )
}

function Chapter({ chapter, index, story }) {
  const last = index === CHAPTERS.length - 1
  const local = useTransform(story, (s) => s - index)
  // The first chapter waits for the scene to finish moving out from under it.
  const fadeIn = index === 0 ? [0.1, 0.26] : [0, 0.14]
  const opacity = useTransform(
    local,
    last ? fadeIn : [...fadeIn, 0.86, 0.98],
    last ? [0, 1] : [0, 1, 1, 0],
  )
  const visibility = useTransform(opacity, hideWhenClear)
  const weight = useSteppedWeight(local, [fadeIn[0], 0.6], [200, 660])
  const tracking = useTransform(local, [fadeIn[0], 0.6], ['0.08em', '-0.03em'])
  const numeralY = useTransform(local, [0, 1], ['14%', '-14%'])
  const bodyOpacity = useTransform(local, [fadeIn[0] + 0.1, fadeIn[0] + 0.3], [0, 1])
  const bodyY = useTransform(local, [fadeIn[0] + 0.1, fadeIn[0] + 0.3], ['1.25rem', '0rem'])

  // Detect: the readout climbs with the scene's score bar and crosses 0.75.
  const scoreRef = useRef(null)
  useMotionValueEvent(story, 'change', (s) => {
    if (!scoreRef.current) return
    const score = 0.12 + 0.81 * smooth(sat((s - 1.05) / 0.45))
    scoreRef.current.textContent = score.toFixed(2)
    scoreRef.current.dataset.hot = score >= 0.75
  })

  // The fades go on each element, not on a shared parent: an ancestor with
  // opacity below 1 cuts the readout's backdrop blur off from the scene behind
  // it, so the panel would go flat for the length of every fade.
  const copyOpacity = useTransform([opacity, bodyOpacity], ([a, c]) => a * c)

  return (
    <motion.article className="ld-chapter" style={{ visibility }}>
      <motion.span
        className="ld-chapter__numeral"
        style={{ y: numeralY, opacity }}
        aria-hidden="true"
      >
        {String(index + 1).padStart(2, '0')}
      </motion.span>
      <motion.h2
        className="ld-chapter__verb"
        style={{ fontWeight: weight, letterSpacing: tracking, opacity }}
      >
        {chapter.verb}
      </motion.h2>
      <motion.div className="ld-chapter__copy" style={{ y: bodyY }}>
        <motion.p className="ld-chapter__body" style={{ opacity: copyOpacity }}>
          {chapter.body}
        </motion.p>
        <motion.dl className="ld-data" style={{ opacity: copyOpacity }}>
          {chapter.data.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value ?? <span ref={scoreRef} className="ld-score">0.12</span>}</dd>
            </div>
          ))}
        </motion.dl>
        {chapter.cta && (
          <motion.div style={{ opacity: copyOpacity }}>
            <DashboardLink />
          </motion.div>
        )}
      </motion.div>
    </motion.article>
  )
}

export default function StoryStage() {
  const stageRef = useRef(null)
  const { scrollYProgress } = useScroll({ target: stageRef, offset: ['start start', 'end end'] })
  const intro = useTransform(scrollYProgress, (p) => sat((p * TRAVEL_VH) / INTRO_VH))
  const story = useTransform(
    scrollYProgress,
    (p) => sat((p * TRAVEL_VH - INTRO_VH) / (TRAVEL_VH - INTRO_VH)) * CHAPTERS.length,
  )

  const portrait = useMediaQuery('(orientation: portrait)')
  const side = useMediaQuery('(min-width: 1024px) and (orientation: landscape)')

  // The live scene sits under the sequence and takes over on its matching frame.
  const [sceneReady, setSceneReady] = useState(false)
  const requestRender = useRef(null)
  const getProgress = useCallback(
    () => ({ intro: LIVE_INTRO ? intro.get() : 1, story: story.get() }),
    [intro, story],
  )
  const onReady = useCallback((invalidate) => {
    requestRender.current = invalidate
    setSceneReady(true)
  }, [])
  useMotionValueEvent(story, 'change', () => requestRender.current?.())
  useMotionValueEvent(intro, 'change', () => LIVE_INTRO && requestRender.current?.())
  const sequenceOpacity = useTransform(intro, (v) => (v >= 1 || LIVE_INTRO ? 0 : 1))

  return (
    <section
      ref={stageRef}
      className="ld-stage"
      style={{ '--ld-travel': TRAVEL_VH }}
      aria-label="How GraphSentinel works"
    >
      <span
        id="pipeline"
        className="ld-anchor"
        style={{ top: `${INTRO_VH + CHAPTER_VH * 0.3}svh` }}
      />
      <div className="ld-sticky">
        <div className="ld-layer">
          <SceneBoundary>
            <Suspense fallback={null}>
              <NetworkCanvas getProgress={getProgress} side={side} onReady={onReady} />
            </Suspense>
          </SceneBoundary>
        </div>
        <motion.div className="ld-layer" style={{ opacity: sceneReady ? sequenceOpacity : 1 }}>
          <SequenceCanvas
            progress={intro}
            set={portrait ? 'mobile' : 'desktop'}
            className="ld-sequence"
          />
        </motion.div>
        <Hero intro={intro} />
        <div className="ld-chapters">
          {CHAPTERS.map((chapter, index) => (
            <Chapter key={chapter.verb} chapter={chapter} index={index} story={story} />
          ))}
        </div>
      </div>
    </section>
  )
}
