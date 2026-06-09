// [Windows] GraphSentinel — Susheep
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'

export default function ThreatTimeline({ data }) {
  return (
    <div className="h-full flex flex-col">
      <h3 className="text-gray-400 font-mono text-xs mb-1 shrink-0">📈 THREAT TIMELINE</h3>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="threats-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ff4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#ff4444" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="blocked-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0066ff" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#0066ff" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 10 }} />
            <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
            <Tooltip
              contentStyle={{
                background: '#111827',
                border: '1px solid #374151',
                borderRadius: '6px',
                fontFamily: 'monospace',
                fontSize: '11px',
              }}
            />
            <Area
              type="monotone"
              dataKey="threats"
              stroke="#ff4444"
              fill="url(#threats-grad)"
              strokeWidth={2}
              dot={false}
              name="Threats"
            />
            <Area
              type="monotone"
              dataKey="blocked"
              stroke="#0066ff"
              fill="url(#blocked-grad)"
              strokeWidth={2}
              dot={false}
              name="Blocked"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
