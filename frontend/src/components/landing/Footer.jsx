// [Windows] GraphSentinel - Susheep
import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="border-t border-gs-border py-10 px-6">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-center md:text-left">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-md bg-gs-accent-soft border border-gs-accent/20 flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="none" className="w-3.5 h-3.5 text-gs-accent" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
            </svg>
          </div>
          <span className="text-[13px] font-heading font-medium text-gs-muted">
            GraphSentinel - Autonomous Cyber Defense
          </span>
        </div>

        <div className="flex items-center gap-6">
          <Link to="/login" className="text-[12px] text-gs-muted hover:text-gs-text transition-colors no-underline">
            Dashboard
          </Link>
          <a href="#pipeline" className="text-[12px] text-gs-muted hover:text-gs-text transition-colors no-underline">
            Architecture
          </a>
          <span className="text-[11px] text-gs-faint font-mono">
            Chain ID: 1337
          </span>
        </div>

        <p className="text-[11px] text-gs-faint font-mono">
          &copy; 2026 GraphSentinel Team
        </p>
      </div>
    </footer>
  )
}
