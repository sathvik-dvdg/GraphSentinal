// [Windows] GraphSentinel - Susheep
import { Fragment, useEffect, useRef } from 'react'
import { ArrowUp } from 'lucide-react'
import DashboardLink from './DashboardLink'
import { CHAPTERS, SYSTEM_FACTS } from './content'

// The navbar leaves once the footer covers this much of the window, and comes
// back once it covers less than the second figure. The gap between them is the
// hysteresis: scrolling inside it changes nothing, so the bar cannot flicker.
const HIDE_NAV_AT = 35
const SHOW_NAV_AT = 20

// Curtain-reveal footer. It is sticky to the bottom of the viewport and sits
// under the page, so the last section slides up to uncover it. It stays in
// normal document order, and when it is taller than the viewport the sticky
// offset (see .ld-footer) pins its top instead so the rest scrolls into view.
export default function Footer() {
  const ref = useRef(null)
  const sentinelRef = useRef(null)

  useEffect(() => {
    const footer = ref.current
    const root = footer.parentElement
    const measure = () => root.style.setProperty('--ld-footer-h', `${footer.offsetHeight}px`)
    const observer = new ResizeObserver(measure)
    observer.observe(footer)
    measure()
    return () => observer.disconnect()
  }, [])

  // One piece of shared state: data-footer on the .ld root, read by the CSS
  // (the navbar hides) and by the navbar itself (its menu closes). The
  // sentinel is a 1px marker on the bottom edge of the page; it is inside the
  // window exactly when the footer has begun to cover it. Two observers with
  // different margins give the hysteresis, and no scroll listener is involved.
  // The top margin is huge so a footer taller than the window, which pushes
  // the sentinel above the top edge, still counts as covered.
  useEffect(() => {
    const sentinel = sentinelRef.current
    const root = sentinel.parentElement
    const margin = (cover) => `100000px 0px -${cover}% 0px`
    const hide = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) root.dataset.footer = 'true'
      },
      { rootMargin: margin(HIDE_NAV_AT) },
    )
    const show = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) root.dataset.footer = 'false'
      },
      { rootMargin: margin(SHOW_NAV_AT) },
    )
    hide.observe(sentinel)
    show.observe(sentinel)
    return () => {
      hide.disconnect()
      show.disconnect()
      delete root.dataset.footer
    }
  }, [])

  // Tabbing into the footer while it is still covered: bring it into view.
  const reveal = () => {
    const end = document.documentElement.scrollHeight - window.innerHeight
    if (window.scrollY < end - 1) window.scrollTo(0, end)
  }

  const backToTop = () => {
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    window.scrollTo({ top: 0, behavior: still ? 'auto' : 'smooth' })
  }

  return (
    <>
      <div ref={sentinelRef} className="ld-footer-sentinel" aria-hidden="true" />
      <footer ref={ref} className="ld-footer" onFocus={reveal}>
        <p className="ld-footer__line">Detect, heal and record, on one machine.</p>

        <ol className="ld-footer__loop" aria-label="The loop">
          {CHAPTERS.map((chapter, index) => (
            <Fragment key={chapter.verb}>
              {index > 0 && <li className="ld-footer__rule" aria-hidden="true" />}
              <li
                className={
                  chapter.verb === 'Heal'
                    ? 'ld-footer__stage ld-footer__stage--heal'
                    : 'ld-footer__stage'
                }
              >
                {chapter.verb}
              </li>
            </Fragment>
          ))}
        </ol>

        <p className="ld-footer__mark" aria-hidden="true">
          GraphSentinel
        </p>

        <div className="ld-footer__cta">
          <DashboardLink id="cta-footer-dashboard" />
        </div>

        <dl className="ld-footer__facts">
          {SYSTEM_FACTS.map((fact) => (
            <div key={fact.label}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>

        <div className="ld-footer__meta">
          <div className="ld-footer__meta-text">
            <span>Built with FastAPI + PyTorch Geometric + Hardhat + React</span>
            <span>&copy; 2026 GraphSentinel Team</span>
          </div>
          <button type="button" className="ld-footer__top-btn" onClick={backToTop}>
            <span>Back to top</span>
            <ArrowUp size={14} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </div>
      </footer>
    </>
  )
}
