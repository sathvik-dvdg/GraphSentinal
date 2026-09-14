// [Windows] GraphSentinel — Susheep
// ui/BlockchainStatusBadge — Canonical presentation for blockchain transaction states
// Guarantees truthful status representation: never defaults to or assumes Confirmed.

const STATUS_CONFIG = {
  confirmed: {
    label: 'Confirmed',
    colorClass: 'bg-gs-heal-soft text-gs-heal border-gs-heal/20',
    dotClass: 'bg-gs-heal',
    pulse: false,
    ariaLabel: 'Blockchain status: Confirmed on-chain',
  },
  pending: {
    label: 'Pending',
    colorClass: 'bg-gs-warn-soft text-gs-warn border-gs-warn/20',
    dotClass: 'bg-gs-warn',
    pulse: true,
    ariaLabel: 'Blockchain status: Pending confirmation',
  },
  submitting: {
    label: 'Submitting',
    colorClass: 'bg-gs-accent-soft text-gs-accent border-gs-accent/20',
    dotClass: 'bg-gs-accent',
    pulse: true,
    ariaLabel: 'Blockchain status: Submitting to ledger',
  },
  retry: {
    label: 'Retrying',
    colorClass: 'bg-gs-warn-soft text-gs-warn border-gs-warn/20',
    dotClass: 'bg-gs-warn',
    pulse: true,
    ariaLabel: 'Blockchain status: Retrying submission',
  },
  retrying: {
    label: 'Retrying',
    colorClass: 'bg-gs-warn-soft text-gs-warn border-gs-warn/20',
    dotClass: 'bg-gs-warn',
    pulse: true,
    ariaLabel: 'Blockchain status: Retrying submission',
  },
  failed: {
    label: 'Failed',
    colorClass: 'bg-gs-threat-soft text-gs-threat border-gs-threat/20',
    dotClass: 'bg-gs-threat',
    pulse: false,
    ariaLabel: 'Blockchain status: Transaction failed',
  },
  error: {
    label: 'Error',
    colorClass: 'bg-gs-threat-soft text-gs-threat border-gs-threat/20',
    dotClass: 'bg-gs-threat',
    pulse: false,
    ariaLabel: 'Blockchain status: Error',
  },
  unavailable: {
    label: 'Unavailable',
    colorClass: 'bg-white/5 text-gs-faint border-white/10',
    dotClass: 'bg-gs-faint',
    pulse: false,
    ariaLabel: 'Blockchain status: Ledger unavailable',
  },
  offline: {
    label: 'Offline',
    colorClass: 'bg-white/5 text-gs-faint border-white/10',
    dotClass: 'bg-gs-faint',
    pulse: false,
    ariaLabel: 'Blockchain status: Offline',
  },
  no_tx: {
    label: 'No TX',
    colorClass: 'bg-white/5 text-gs-faint border-white/10',
    dotClass: null,
    pulse: false,
    ariaLabel: 'Blockchain status: No transaction',
  },
}

export default function BlockchainStatusBadge({ status, className = '' }) {
  const normalizedKey = typeof status === 'string' ? status.trim().toLowerCase() : ''
  const config = STATUS_CONFIG[normalizedKey]

  if (config) {
    return (
      <span
        role="status"
        aria-label={config.ariaLabel}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md border text-[10px] font-mono font-medium ${config.colorClass} ${className}`}
      >
        {config.dotClass && (
          <span
            className={`w-1 h-1 rounded-full ${config.dotClass} ${config.pulse ? 'animate-pulse' : ''}`}
            aria-hidden="true"
          />
        )}
        {config.label}
      </span>
    )
  }

  // Safe fallback for null, undefined, or unrecognized statuses
  const displayLabel = status ? String(status).slice(0, 16) : 'Unknown'
  return (
    <span
      role="status"
      aria-label={`Blockchain status: ${displayLabel}`}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md border bg-white/5 text-gs-faint border-white/10 text-[10px] font-mono font-medium ${className}`}
    >
      <span className="w-1 h-1 rounded-full bg-gs-faint" aria-hidden="true" />
      {displayLabel}
    </span>
  )
}
