// [Windows] GraphSentinel — Susheep
// SimBadge — kept for any legacy imports; ConnectionModeBadge is the preferred component
export default function SimBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 bg-gs-warn-soft text-gs-warn border border-gs-warn/30 px-2.5 py-1 rounded-md text-[10px] font-mono tracking-wider uppercase">
      <span className="w-1.5 h-1.5 rounded-full bg-gs-warn animate-pulse flex-shrink-0" aria-hidden="true" />
      SIMULATION
    </span>
  )
}
