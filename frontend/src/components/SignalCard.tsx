import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'

const CONF_COLOR: Record<string, string> = {
  HIGH: 'border-green-500 bg-green-500/10',
  MEDIUM: 'border-yellow-500 bg-yellow-500/10',
}
const CONF_BADGE: Record<string, string> = {
  HIGH: 'bg-green-500/20 text-green-400',
  MEDIUM: 'bg-yellow-500/20 text-yellow-400',
}
const TREND_ARROW: Record<string, string> = { up: '↑', down: '↓' }

export default function SignalCard({ signal }: { signal: any }) {
  const [expanded, setExpanded] = useState(false)
  const conf = (signal.confidence || 'MEDIUM').toUpperCase()

  const { data: priceData } = useQuery({
    queryKey: ['prices', signal.id],
    queryFn: () => fetch(`/api/signals/${signal.id}/prices`).then(r => r.json()),
    enabled: expanded,
  })

  const upside = signal.price_target && signal.current_price
    ? `+${(((signal.price_target - signal.current_price) / signal.current_price) * 100).toFixed(1)}%`
    : null

  return (
    <div
      className={`border rounded-xl p-4 cursor-pointer transition hover:border-opacity-80 ${CONF_COLOR[conf] || 'border-gray-700 bg-gray-900'}`}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-white">{signal.ticker}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CONF_BADGE[conf]}`}>{conf}</span>
            {signal.earnings_within_7d && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">📅 Earnings</span>
            )}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">{signal.name} · {signal.sector}</div>
        </div>
        <div className="text-right">
          <div className="text-white font-semibold">${signal.current_price}</div>
          <div className={`text-sm font-medium ${signal.wow_change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {signal.wow_change_pct >= 0 ? '↑' : '↓'} {Math.abs(signal.wow_change_pct).toFixed(2)}% WoW
          </div>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <Metric label="vs S&P 500" value={signal.relative_strength_vs_spy != null ? `${signal.relative_strength_vs_spy >= 0 ? '+' : ''}${signal.relative_strength_vs_spy?.toFixed(1)}%` : 'N/A'} />
        <Metric label="Volume" value={signal.volume_ratio ? `${signal.volume_ratio}x` : 'N/A'} />
        <Metric label="Sentiment" value={signal.sentiment_score != null ? (signal.sentiment_score >= 0 ? `+${signal.sentiment_score?.toFixed(2)}` : signal.sentiment_score?.toFixed(2)) : 'N/A'} />
      </div>

      {/* Trend arrows */}
      <div className="flex gap-3 text-xs text-gray-400 mb-3">
        <span>1d <span className={signal.trend_1d === 'up' ? 'text-green-400' : 'text-red-400'}>{TREND_ARROW[signal.trend_1d] || '?'}</span></span>
        <span>1w <span className={signal.trend_1w === 'up' ? 'text-green-400' : 'text-red-400'}>{TREND_ARROW[signal.trend_1w] || '?'}</span></span>
        <span>1m <span className={signal.trend_1m === 'up' ? 'text-green-400' : 'text-red-400'}>{TREND_ARROW[signal.trend_1m] || '?'}</span></span>
        {upside && <span className="ml-auto text-green-400">🎯 {upside} target</span>}
      </div>

      {/* Analysis reason */}
      <p className="text-xs text-gray-300 leading-relaxed">{signal.reason}</p>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-700 space-y-3">
          {/* Sparkline */}
          {priceData?.prices?.length > 0 && (
            <div className="h-20">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={priceData.prices}>
                  <Line type="monotone" dataKey="price" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: 'none', fontSize: '11px' }}
                    formatter={(v: any) => [`$${v}`, 'Price']}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Target / Stop */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-green-500/10 rounded-lg p-2">
              <div className="text-gray-400">🎯 Target</div>
              <div className="text-green-400 font-semibold">${signal.price_target ?? 'N/A'}</div>
            </div>
            <div className="bg-red-500/10 rounded-lg p-2">
              <div className="text-gray-400">🛑 Stop Loss</div>
              <div className="text-red-400 font-semibold">${signal.stop_loss ?? 'N/A'}</div>
            </div>
          </div>

          {/* Risk */}
          <div className="text-xs text-gray-400">
            <span className="text-gray-500">⚠️ Risk: </span>{signal.risk}
          </div>

          {/* News */}
          {signal.news?.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs text-gray-500 font-medium">Recent News</div>
              {signal.news.map((n: any, i: number) => (
                <div key={i} className="text-xs text-gray-300 flex gap-2">
                  <span className={`shrink-0 ${n.sentiment === 'POSITIVE' ? 'text-green-400' : n.sentiment === 'NEGATIVE' ? 'text-red-400' : 'text-gray-500'}`}>
                    {n.sentiment === 'POSITIVE' ? '●' : n.sentiment === 'NEGATIVE' ? '●' : '○'}
                  </span>
                  <span>{n.title}</span>
                </div>
              ))}
            </div>
          )}

          <div className="text-xs text-gray-600 text-right">
            {new Date(signal.signaled_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900/60 rounded-lg p-2 text-center">
      <div className="text-gray-500 text-xs">{label}</div>
      <div className="text-white text-xs font-medium">{value}</div>
    </div>
  )
}
