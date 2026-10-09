import { useEffect } from 'react'
import { useReducedMotion } from 'framer-motion'
import Navbar from './Navbar'
import Footer from './Footer'
import StoryStage from './StoryStage'
import StaticStory from './StaticStory'
import { Metrics, Team, Threats } from './Specimen'
import './landing.css'

// The landing page itself, with no routing or auth concerns: those live in
// pages/LandingPage.jsx. Keeping it separate also lets the dev preview under
// scripts/landing-preview mount it on its own.
export default function LandingView() {
  const reduce = useReducedMotion()

  // The app shell paints its own body colour; the landing page paints its own
  // ground while it is on screen.
  useEffect(() => {
    document.documentElement.classList.add('ld-active')
    return () => document.documentElement.classList.remove('ld-active')
  }, [])

  return (
    <div className="ld">
      <Navbar />
      <main className="ld-main">
        {reduce ? <StaticStory /> : <StoryStage />}
        <Threats reduce={reduce} />
        <Metrics reduce={reduce} />
        <Team />
      </main>
      <Footer />
    </div>
  )
}
