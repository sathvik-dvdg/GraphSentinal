// [Windows] GraphSentinel - Susheep
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Menu, X } from 'lucide-react'

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
      style={{
        backgroundColor: scrolled || menuOpen ? 'rgba(255,255,255,0.90)' : 'rgba(255,255,255,0.80)',
        borderBottom: scrolled || menuOpen ? '1px solid #e2e5ea' : '1px solid rgba(226,229,234,0.6)',
        backdropFilter: 'blur(12px)',
      }}
    >
      <nav
        className="w-full max-w-6xl mx-auto flex items-center justify-between px-4 sm:px-6 h-14"
        aria-label="Main navigation"
      >
        <Link
          to="/"
          className="flex items-center gap-2.5 no-underline group"
          aria-label="GraphSentinel home"
        >
          <div className="w-7 h-7 rounded-lg bg-gs-accent-soft border border-gs-accent/25 flex items-center justify-center transition-colors group-hover:bg-gs-accent/20">
            <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 text-gs-accent" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
            </svg>
          </div>
          <span className="font-heading font-semibold text-sm text-gs-text tracking-wide">
            GraphSentinel
          </span>
        </Link>

        <div className="hidden md:flex items-center gap-6">
          <a href="#pipeline" className="text-[13px] text-gs-muted hover:text-gs-text transition-colors duration-200 no-underline">
            Architecture
          </a>
          <a href="#capabilities" className="text-[13px] text-gs-muted hover:text-gs-text transition-colors duration-200 no-underline">
            Capabilities
          </a>
          <a href="#threats" className="text-[13px] text-gs-muted hover:text-gs-text transition-colors duration-200 no-underline">
            Threats
          </a>
          <Link
            to="/login"
            id="navbar-dashboard-link"
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-gs-heal text-white text-[13px] font-heading font-medium hover:bg-gs-heal/90 transition-colors duration-200 no-underline"
          >
            Dashboard -&gt;
          </Link>
        </div>

        <button
          id="navbar-mobile-toggle"
          className="md:hidden text-gs-muted hover:text-gs-text transition-colors p-1"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
        >
          {menuOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
      </nav>

      {menuOpen && (
        <div
          className="md:hidden border-t border-gs-border"
          style={{ backgroundColor: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(12px)' }}
        >
          <div className="flex flex-col px-6 py-4 gap-3">
            <a href="#pipeline" className="text-sm text-gs-muted hover:text-gs-text transition-colors no-underline" onClick={() => setMenuOpen(false)}>
              Architecture
            </a>
            <a href="#capabilities" className="text-sm text-gs-muted hover:text-gs-text transition-colors no-underline" onClick={() => setMenuOpen(false)}>
              Capabilities
            </a>
            <a href="#threats" className="text-sm text-gs-muted hover:text-gs-text transition-colors no-underline" onClick={() => setMenuOpen(false)}>
              Threats
            </a>
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gs-heal text-white text-sm font-heading font-medium hover:bg-gs-heal/90 transition-colors no-underline w-full justify-center"
              onClick={() => setMenuOpen(false)}
            >
              Open Dashboard -&gt;
            </Link>
          </div>
        </div>
      )}
    </header>
  )
}
