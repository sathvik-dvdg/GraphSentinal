// [Windows] GraphSentinel — Susheep
// ui/DemoModeBadge — Decision #12 (decisions.md), Option B: demo_flows()
// stays in the backend as a documented, opt-in "no-Mininet demo path," but
// it must never be invisible — this makes it impossible to mistake synthetic
// fallback traffic for a real capture. Shows whenever the backend is
// *configured* to allow demo fallback (stats.demo_fallback_flows), not only
// while it's actively substituting data — the operational risk is running a
// deployment where it's silently possible, not just where it's active right now.
export default function DemoModeBadge({ demoFallbackFlows, className = '' }) {
  if (!demoFallbackFlows) return null

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-mono text-[10px] font-medium tracking-wider badge-sim ${className}`}
      role="status"
      title="This backend is configured to fall back to synthetic demo traffic if the OVS daemon is unreachable (DEMO_FALLBACK_FLOWS=true)"
    >
      DEMO MODE — SYNTHETIC TRAFFIC ALLOWED
    </span>
  )
}
