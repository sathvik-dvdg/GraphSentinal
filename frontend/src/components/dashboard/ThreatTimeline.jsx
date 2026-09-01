// [Windows] GraphSentinel — Susheep
// ThreatTimeline — updated chart colors to new token system
// ── All props and data bindings preserved verbatim ──
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'

export default function ThreatTimeline({ data }) {
  return (
    <div className="h-full flex flex-col px-1 pt-2">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5 shrink-0">
        <span className="text-[9px] font-mono text-gs-faint tracking-widest uppercase">
          Threat Timeline
        </span>
        <div className="h-px flex-1 bg-gs-border" />
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-1 rounded-full" style={{ backgroundColor: '#E03C3C80' }} />
            <span className="text-[9px] font-mono text-gs-muted">Threats</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-1 rounded-full" style={{ backgroundColor: '#2ECC8A80' }} />
            <span className="text-[9px] font-mono text-gs-muted">Blocked</span>
          </div>
        </div>
      </div>

      {/* Chart — all original recharts props preserved */}
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <defs>
              {/* Original gradient IDs preserved */}
              <linearGradient id="threats-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#E03C3C" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#E03C3C" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="blocked-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#12a672" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#12a672" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(226,229,234,0.9)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fill: '#9aa1ad', fontSize: 9, fontFamily: '"DM Mono", monospace' }}
              axisLine={{ stroke: 'rgba(226,229,234,0.8)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#9aa1ad', fontSize: 9, fontFamily: '"DM Mono", monospace' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: '#f0f2f5',
                border: '1px solid #e2e5ea',
                borderRadius: '8px',
                fontFamily: '"DM Mono", monospace',
                fontSize: '10px',
                color: '#1b1f27',
                boxShadow: '0 8px 24px rgba(17,20,26,0.10)',
              }}
              itemStyle={{ color: '#5a616e' }}
              cursor={{ stroke: 'rgba(79,110,247,0.3)', strokeDasharray: '3 3' }}
            />
            {/* Original Area components — dataKey, stroke, fill preserved */}
            <Area
              type="monotone"
              dataKey="threats"
              stroke="#E03C3C"
              fill="url(#threats-grad)"
              strokeWidth={1.5}
              dot={false}
              name="Threats"
            />
            <Area
              type="monotone"
              dataKey="blocked"
              stroke="#12a672"
              fill="url(#blocked-grad)"
              strokeWidth={1.5}
              dot={false}
              name="Blocked"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
