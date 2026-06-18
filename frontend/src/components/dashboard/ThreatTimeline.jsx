// [Windows] GraphSentinel — Susheep
// ── All props and data bindings preserved verbatim ──
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'

export default function ThreatTimeline({ data }) {
  return (
    <div className="h-full flex flex-col px-1 pt-1.5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5 shrink-0">
        <span className="text-[9px] font-mono text-slate-600 tracking-widest uppercase">Threat Timeline</span>
        <div className="h-px flex-1 bg-gradient-to-r from-slate-800 to-transparent" />
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-2 h-1 rounded-full bg-rose-500/60" />
            <span className="text-[9px] font-mono text-slate-600">Threats</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-1 rounded-full bg-cyan-500/60" />
            <span className="text-[9px] font-mono text-slate-600">Blocked</span>
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
                <stop offset="5%"  stopColor="#f43f5e" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="blocked-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#06b6d4" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(30,41,59,0.6)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fill: '#475569', fontSize: 9, fontFamily: 'JetBrains Mono, monospace' }}
              axisLine={{ stroke: 'rgba(30,41,59,0.5)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#475569', fontSize: 9, fontFamily: 'JetBrains Mono, monospace' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(15,23,42,0.92)',
                border: '1px solid rgba(30,41,59,0.8)',
                borderRadius: '8px',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '10px',
                color: '#e2e8f0',
                boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                backdropFilter: 'blur(12px)',
              }}
              itemStyle={{ color: '#94a3b8' }}
              cursor={{ stroke: 'rgba(6,182,212,0.3)', strokeDasharray: '3 3' }}
            />
            {/* Original Area components — dataKey, stroke, fill preserved */}
            <Area
              type="monotone"
              dataKey="threats"
              stroke="#f43f5e"
              fill="url(#threats-grad)"
              strokeWidth={1.5}
              dot={false}
              name="Threats"
            />
            <Area
              type="monotone"
              dataKey="blocked"
              stroke="#06b6d4"
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
