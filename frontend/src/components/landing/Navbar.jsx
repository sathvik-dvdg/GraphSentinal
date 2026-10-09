// [Windows] GraphSentinel - Susheep
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import DashboardLink from './DashboardLink'
import { NAV_LINKS } from './content'

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false)
  const close = () => setMenuOpen(false)
  const ref = useRef(null)

  // The footer sets data-footer on the .ld root (see Footer.jsx) and the CSS
  // hides this bar while it is 'true'. A menu left open would come back with
  // the bar, so it closes as the footer arrives.
  useEffect(() => {
    const root = ref.current.closest('.ld')
    if (!root) return undefined
    const observer = new MutationObserver(() => {
      if (root.dataset.footer === 'true') setMenuOpen(false)
    })
    observer.observe(root, { attributes: true, attributeFilter: ['data-footer'] })
    return () => observer.disconnect()
  }, [])

  return (
    <header ref={ref} className="ld-nav" data-open={menuOpen}>
      <nav className="ld-nav__bar" aria-label="Main navigation">
        <Link to="/" className="ld-nav__mark" aria-label="GraphSentinel home">
          GraphSentinel
        </Link>

        <div className="ld-nav__links">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
          <DashboardLink id="navbar-dashboard-link" compact />
        </div>

        <button
          id="navbar-mobile-toggle"
          type="button"
          className="ld-nav__toggle"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          aria-controls="ld-nav-menu"
        >
          {menuOpen ? <X size={20} strokeWidth={1.5} /> : <Menu size={20} strokeWidth={1.5} />}
        </button>
      </nav>

      {menuOpen && (
        <div id="ld-nav-menu" className="ld-nav__menu">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} onClick={close}>
              {link.label}
            </a>
          ))}
          <DashboardLink onClick={close} />
        </div>
      )}
    </header>
  )
}
