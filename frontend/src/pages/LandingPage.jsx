// [Windows] GraphSentinel — Susheep
import Navbar from '../components/landing/Navbar'
import HeroSection from '../components/landing/HeroSection'
import SystemFlow from '../components/landing/SystemFlow'
import FeatureGrid from '../components/landing/FeatureGrid'
import AttackStats from '../components/landing/AttackStats'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gs-bg">
      <Navbar />
      <HeroSection />
      <SystemFlow />
      <FeatureGrid />
      <AttackStats />

      {/* Footer */}
      <footer className="py-12 px-6 bg-gs-bg border-t border-gs-border">
        <div className="max-w-6xl mx-auto text-center">
          <p className="text-gs-accent font-mono text-sm mb-3">
            🛡️ GraphSentinel · Major Project · Local Demo Only
          </p>
          <p className="text-gray-600 text-xs font-mono mb-2">
            Sairaj · Susheep · Skanda · Sathvik
          </p>
          <p className="text-gray-700 text-xs font-mono">
            FastAPI · PyTorch · Hardhat · React 18
          </p>
        </div>
      </footer>
    </div>
  )
}
