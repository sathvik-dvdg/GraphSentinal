import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { CTA_LABEL } from './content'

// The page's single call to action. Same label and destination everywhere.
export default function DashboardLink({ id, compact = false, onClick }) {
  return (
    <Link
      to="/login"
      id={id}
      onClick={onClick}
      className={`ld-cta${compact ? ' ld-cta--compact' : ''}`}
    >
      <span>{CTA_LABEL}</span>
      <span className="ld-cta__icon" aria-hidden="true">
        <ArrowUpRight size={compact ? 14 : 16} strokeWidth={1.5} />
      </span>
    </Link>
  )
}
