import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { ATTACKS, HEADLINE_METRIC, METRICS, TEAM } from './content'
import { useSteppedWeight } from './typeScrub'

// Type weight scrubbed by the section's own scroll position. Under reduced
// motion the settled weight is applied directly.
function ScrubbedType({ as = 'h3', progress, weight, className, children }) {
  const fontWeight = useSteppedWeight(progress, [0, 1], [200, weight])
  const letterSpacing = useTransform(progress, [0, 1], ['0.05em', '-0.025em'])
  const Tag = motion[as]
  return (
    <Tag className={className} style={{ fontWeight, letterSpacing }}>
      {children}
    </Tag>
  )
}

function useSectionScrub(offset) {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset })
  return [ref, scrollYProgress]
}

export function Threats({ reduce }) {
  const [ref, progress] = useSectionScrub(['start 0.9', 'start 0.15'])
  return (
    <section id="threats" className="ld-section" ref={ref}>
      <header className="ld-section__head">
        <h2 className="ld-display">Five attacks, five signals.</h2>
        <p className="ld-lede">
          Trained on <span className="ld-mono">575,000+</span> CICIDS2017 network flow records.
        </p>
      </header>
      <ul className="ld-attacks">
        {ATTACKS.map((attack) => (
          <li key={attack.name}>
            {reduce ? (
              <h3 className="ld-attack__name" style={{ fontWeight: attack.weight }}>
                {attack.name}
              </h3>
            ) : (
              <ScrubbedType progress={progress} weight={attack.weight} className="ld-attack__name">
                {attack.name}
              </ScrubbedType>
            )}
            <p className="ld-attack__signal">{attack.signal}</p>
            <p className="ld-attack__dataset">{attack.dataset}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function Metrics({ reduce }) {
  const [ref, progress] = useSectionScrub(['start 0.9', 'center center'])
  return (
    <section className="ld-section ld-metrics" ref={ref} aria-label="Headline metrics">
      <div className="ld-metrics__lead">
        {reduce ? (
          <p className="ld-metrics__hero" style={{ fontWeight: 520 }}>
            {HEADLINE_METRIC.value}
          </p>
        ) : (
          <ScrubbedType as="p" progress={progress} weight={520} className="ld-metrics__hero">
            {HEADLINE_METRIC.value}
          </ScrubbedType>
        )}
        <p className="ld-metrics__label">{HEADLINE_METRIC.label}</p>
      </div>
      <dl className="ld-metrics__grid">
        {METRICS.map((metric) => (
          <div key={metric.label}>
            <dd className={metric.threat ? 'ld-metric ld-metric--threat' : 'ld-metric'}>
              {metric.value}
            </dd>
            <dt className="ld-metrics__label">{metric.label}</dt>
          </div>
        ))}
      </dl>
    </section>
  )
}

export function Team() {
  return (
    <section id="team" className="ld-section">
      <header className="ld-section__head">
        <h2 className="ld-display">Built by four.</h2>
        <p className="ld-lede">
          A major project that runs entirely on one local machine. No cloud, no deployment.
        </p>
      </header>
      <ul className="ld-team">
        {TEAM.map((member) => (
          <li key={member.name}>
            <h3 className="ld-team__name">{member.name}</h3>
            <p className="ld-team__role">{member.role}</p>
            <p className="ld-team__tech">{member.tech}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
