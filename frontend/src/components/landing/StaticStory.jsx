import DashboardLink from './DashboardLink'
import LiquidCard from './LiquidCard'
import { CHAPTERS, FRAME_COUNT, PREMISE, frameUrl, stillUrl } from './content'
import { LANDSCAPE_FRAME } from './framing'

// Reduced-motion version of the cinematic and the story: one still frame for
// the hero, then every chapter laid out in normal flow with a still figure.
export default function StaticStory() {
  return (
    <>
      <section className="ld-static-hero">
        <img
          src={frameUrl('desktop', FRAME_COUNT - 1)}
          alt="A network of ten hosts around a switch. One host is crimson."
          width={LANDSCAPE_FRAME.width}
          height={LANDSCAPE_FRAME.height}
          className="ld-static-hero__still"
        />
        <div className="ld-hero ld-hero--static">
          <h1 className="ld-hero__title">GraphSentinel</h1>
          <div className="ld-hero__row">
            <LiquidCard quiet className="ld-hero__card">
              <p className="ld-hero__premise">{PREMISE}</p>
            </LiquidCard>
            <DashboardLink id="hero-cta-dashboard" />
          </div>
        </div>
      </section>

      <div id="pipeline" className="ld-static-story">
        {CHAPTERS.map((chapter, index) => (
          <article key={chapter.verb} className="ld-static-chapter">
            <div className="ld-chapter ld-chapter--static">
              <span className="ld-chapter__numeral" aria-hidden="true">
                {String(index + 1).padStart(2, '0')}
              </span>
              <h2 className="ld-chapter__verb">{chapter.verb}</h2>
              <div className="ld-chapter__copy">
                <p className="ld-chapter__body">{chapter.body}</p>
                <dl className="ld-data">
                  {chapter.data.map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value ?? <span className="ld-score" data-hot="true">above 0.75</span>}</dd>
                    </div>
                  ))}
                </dl>
                {chapter.cta && <DashboardLink />}
              </div>
            </div>
            <img
              src={stillUrl(index + 1)}
              alt={chapter.alt}
              width="1200"
              height="900"
              loading="lazy"
              className="ld-static-chapter__figure"
            />
          </article>
        ))}
      </div>
    </>
  )
}
