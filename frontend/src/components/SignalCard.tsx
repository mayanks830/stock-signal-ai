import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AreaChart, Area, ReferenceLine, ResponsiveContainer, Tooltip } from 'recharts'

const SIGNAL_TYPE_LABEL: Record<string, string> = {
  MOMENTUM: 'Momentum',
  EARLY: 'Early Signal',
  DIP_BUY: 'Buy the Dip',
  PULLBACK: 'Pullback',
  CONGRESS: 'Congress',
}

const SIGNAL_BADGE: Record<string, { label: string; bg: string; text: string }> = {
  BUY: { label: 'BUY', bg: 'bg-green-600', text: 'text-white' },
  SELL: { label: 'SELL', bg: 'bg-red-600', text: 'text-white' },
  HOLD: { label: 'HOLD', bg: 'bg-gray-600', text: 'text-white' },
  CONFLICTED: { label: 'CONFLICTED', bg: 'bg-orange-500', text: 'text-white' },
}

function parseConfidence(raw: any): number {
  if (!raw) return 5
  if (raw === 'HIGH') return 8
  if (raw === 'MEDIUM') return 6
  return parseInt(raw) || 5
}

function getCardBorder(signal: string): string {
  if (signal === 'CONFLICTED') return 'border-l-orange-500'
  if (signal === 'SELL') return 'border-l-red-500'
  if (signal === 'BUY') return 'border-l-green-500'
  return 'border-l-gray-500'
}

export default function SignalCard({ signal, rank }: { signal: any; rank?: number }) {
  const [expanded, setExpanded] = useState(false)

  const confNum = parseConfidence(signal.confidence)
  const signalAction = signal.signal || 'BUY'
  const badge = SIGNAL_BADGE[signalAction] || SIGNAL_BADGE.HOLD

  const { data: priceData } = useQuery({
    queryKey: ['prices', signal.id],
    queryFn: () => fetch(`/api/signals/${signal.id}/prices`).then(r => r.json()),
    enabled: expanded,
  })

  const entryPrice = signal.current_price
  const targetPrice = signal.price_target
  const stopPrice = signal.stop_loss

  const upsidePct = targetPrice && entryPrice
    ? ((targetPrice - entryPrice) / entryPrice * 100).toFixed(1)
    : null
  const downsidePct = stopPrice && entryPrice
    ? ((stopPrice - entryPrice) / entryPrice * 100).toFixed(1)
    : null
  const riskReward = targetPrice && stopPrice && entryPrice && stopPrice !== entryPrice
    ? Math.abs((targetPrice - entryPrice) / (entryPrice - stopPrice)).toFixed(1)
    : null

  const pctChange = signal.pct_change ?? 0
  const isPositive = pctChange >= 0

  const latestPrice = priceData?.prices?.length > 0
    ? priceData.prices[priceData.prices.length - 1].price
    : null
  const chartColor = (latestPrice != null ? latestPrice >= entryPrice : true) ? '#22c55e' : '#ef4444'

  const analysis = signal.analysis || {}
  const conflicts = analysis.conflicts || []
  const dataGaps = analysis.data_gaps || []

  // One-line catalyst text
  const catalystLine = analysis.catalyst || signal.reason || ''

  return (
    <div className={`border border-border rounded-xl overflow-hidden transition hover:border-opacity-80 border-l-4 ${getCardBorder(signalAction)}`}>
      {/* === COLLAPSED VIEW (always visible) === */}
      <div className="p-4 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        {/* Row 1: Rank + Signal Badge + Confidence + Type */}
        <div className="flex items-center gap-3 mb-3">
          {rank != null && (
            <span className="text-sm font-bold text-content-faint w-7 shrink-0">#{rank}</span>
          )}
          <span className={`text-xl font-black px-4 py-1 rounded-lg ${badge.bg} ${badge.text}`}>
            {badge.label}
          </span>
          <span className="text-lg font-bold text-blue-400">{confNum}/10</span>
          {signal.signal_type && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-blue-500/15 text-blue-400 font-medium">
              {SIGNAL_TYPE_LABEL[signal.signal_type] || signal.signal_type}
            </span>
          )}
          {signal.outcome && signal.outcome !== 'OPEN' && (
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${
              signal.outcome === 'WIN' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
            }`}>{signal.outcome}</span>
          )}
        </div>

        {/* Row 2: Ticker + Company + Sector */}
        <div className="flex items-baseline gap-2 mb-3">
          <span className="text-lg font-bold text-content-primary">{signal.ticker}</span>
          {signal.name && <span className="text-sm text-content-muted">{signal.name}</span>}
          {signal.sector && <span className="text-xs text-content-faint">· {signal.sector}</span>}
          {signal.earnings_within_7d && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400">Earnings Soon</span>
          )}
        </div>

        {/* Row 3: Price pills — Entry / Target / Stop */}
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <div className="bg-surface-secondary rounded-lg px-3 py-1.5">
            <div className="text-xs text-content-faint">Entry</div>
            <div className="text-base font-semibold text-content-primary">${entryPrice}</div>
          </div>
          {targetPrice && (
            <div className="bg-surface-secondary rounded-lg px-3 py-1.5">
              <div className="text-xs text-content-faint">Target</div>
              <div className="text-base font-semibold text-content-primary">
                ${targetPrice}
                {upsidePct && <span className="text-green-400 text-sm ml-1">+{upsidePct}%</span>}
              </div>
            </div>
          )}
          {stopPrice && (
            <div className="bg-surface-secondary rounded-lg px-3 py-1.5">
              <div className="text-xs text-content-faint">Stop</div>
              <div className="text-base font-semibold text-content-primary">
                ${stopPrice}
                {downsidePct && <span className="text-red-400 text-sm ml-1">{downsidePct}%</span>}
              </div>
            </div>
          )}
          {riskReward && (
            <div className="bg-surface-secondary rounded-lg px-3 py-1.5">
              <div className="text-xs text-content-faint">R:R</div>
              <div className="text-base font-semibold text-blue-400">{riskReward}:1</div>
            </div>
          )}
        </div>

        {/* Row 4: P&L return bar */}
        <div className="mb-3">
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-surface-tertiary rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
                style={{ width: `${Math.min(Math.abs(pctChange) * 5, 100)}%` }}
              />
            </div>
            <span className={`text-sm font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
              {isPositive ? '+' : ''}{pctChange.toFixed(2)}%
            </span>
          </div>
        </div>

        {/* Row 5: One-line catalyst */}
        {catalystLine && (
          <p className="text-sm text-content-secondary line-clamp-1 mb-3">
            {catalystLine}
          </p>
        )}

        {/* Row 6: Expand trigger */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-content-faint">
            {new Date(signal.signaled_at).toLocaleDateString()}
          </span>
          <span className="text-sm text-blue-400 font-medium">
            {expanded ? '- Hide Analysis' : '+ View Analysis'}
          </span>
        </div>
      </div>

      {/* === EXPANDED VIEW (on click) === */}
      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3 space-y-4">
          {/* Chart */}
          {priceData?.prices?.length > 0 && (
            <div className="h-[140px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={priceData.prices}>
                  <defs>
                    <linearGradient id={`grad-${signal.id}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={chartColor} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={chartColor} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="price"
                    stroke={chartColor}
                    strokeWidth={1.5}
                    fill={`url(#grad-${signal.id})`}
                    dot={false}
                  />
                  <ReferenceLine
                    y={entryPrice}
                    stroke="#6b7280"
                    strokeDasharray="4 3"
                    label={{ value: `Entry $${entryPrice}`, position: 'right', fill: '#9ca3af', fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'rgb(var(--color-bg-secondary))', border: '1px solid rgb(var(--color-border-subtle))', fontSize: '12px' }}
                    formatter={(v: any) => [`$${v}`, 'Price']}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Metrics grid */}
          <div className="grid grid-cols-3 gap-2">
            <Metric label="vs S&P 500" value={signal.relative_strength_vs_spy != null ? `${signal.relative_strength_vs_spy >= 0 ? '+' : ''}${signal.relative_strength_vs_spy?.toFixed(1)}%` : 'N/A'} />
            <Metric label="Volume" value={signal.volume_ratio ? `${signal.volume_ratio}x` : 'N/A'} />
            <Metric label="Sentiment" value={signal.sentiment_score != null ? (signal.sentiment_score >= 0 ? `+${signal.sentiment_score?.toFixed(2)}` : signal.sentiment_score?.toFixed(2)) : 'N/A'} />
          </div>

          {/* Trend arrows */}
          <div className="flex gap-4 text-sm text-content-muted">
            <TrendItem label="1d" direction={signal.trend_1d} />
            <TrendItem label="1w" direction={signal.trend_1w} />
            <TrendItem label="1m" direction={signal.trend_1m} />
          </div>

          {/* Conflicts warning */}
          {conflicts.length > 0 && (
            <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3">
              <div className="text-sm font-bold text-orange-400 mb-1">Conflicts</div>
              {conflicts.map((c: string, i: number) => (
                <p key={i} className="text-sm text-orange-300/80 leading-relaxed">- {c}</p>
              ))}
            </div>
          )}

          {/* Structured Analysis */}
          {(analysis.business_model || analysis.bull_case) && (
            <div className="space-y-3">
              {/* Company Profile */}
              {(analysis.business_model || analysis.valuation) && (
                <div className="bg-surface-secondary/60 rounded-lg p-3">
                  <div className="text-xs font-medium text-content-faint mb-2">Company Profile</div>
                  <div className="space-y-1.5 text-sm">
                    {analysis.business_model && (
                      <div className="flex gap-2">
                        <span className="text-content-faint font-medium w-20 shrink-0">Business</span>
                        <span className="text-content-secondary">{analysis.business_model}</span>
                      </div>
                    )}
                    {analysis.valuation && (
                      <div className="flex gap-2">
                        <span className="text-content-faint font-medium w-20 shrink-0">Valuation</span>
                        <span className="text-content-secondary">{analysis.valuation}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Technicals & Sentiment */}
              {(analysis.technicals?.summary || analysis.sentiment?.summary) && (
                <div className="grid grid-cols-2 gap-2">
                  {analysis.technicals?.summary && (
                    <div className="bg-surface-secondary/60 rounded-lg p-3">
                      <div className="text-xs font-medium text-content-faint mb-1">Technicals</div>
                      <p className="text-sm text-content-secondary leading-relaxed">{analysis.technicals.summary}</p>
                      {analysis.technicals.indicators?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {analysis.technicals.indicators.map((ind: string, i: number) => (
                            <span key={i} className="text-xs px-1.5 py-0.5 rounded bg-surface-secondary text-content-muted">{ind}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {analysis.sentiment?.summary && (
                    <div className="bg-surface-secondary/60 rounded-lg p-3">
                      <div className="text-xs font-medium text-content-faint mb-1">Sentiment</div>
                      <p className="text-sm text-content-secondary leading-relaxed">{analysis.sentiment.summary}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Bull / Bear cases */}
              {(analysis.bull_case || analysis.bear_case) && (
                <div className="grid grid-cols-2 gap-2">
                  {analysis.bull_case && (
                    <div className="bg-green-500/5 border border-green-500/15 rounded-lg p-3">
                      <div className="text-xs font-medium text-green-400 mb-1">Bull Case</div>
                      <p className="text-sm text-content-secondary leading-relaxed">{analysis.bull_case}</p>
                    </div>
                  )}
                  {analysis.bear_case && (
                    <div className="bg-red-500/5 border border-red-500/15 rounded-lg p-3">
                      <div className="text-xs font-medium text-red-400 mb-1">Bear Case</div>
                      <p className="text-sm text-content-secondary leading-relaxed">{analysis.bear_case}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Invalidation + Upcoming Events */}
              {(analysis.invalidation || analysis.upcoming_events?.length > 0) && (
                <div className="bg-surface-secondary/60 rounded-lg p-3 space-y-1.5">
                  {analysis.invalidation && (
                    <div className="text-sm">
                      <span className="text-red-400 font-medium">Invalidation: </span>
                      <span className="text-content-secondary">{analysis.invalidation}</span>
                    </div>
                  )}
                  {analysis.upcoming_events?.length > 0 && (
                    <div className="text-sm">
                      <span className="text-orange-400 font-medium">Upcoming: </span>
                      <span className="text-content-secondary">{analysis.upcoming_events.join(' | ')}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Recommendation */}
              {analysis.recommendation && (
                <div className="bg-blue-500/8 border border-blue-500/15 rounded-lg p-3">
                  <p className="text-sm text-blue-300 leading-relaxed">{analysis.recommendation}</p>
                </div>
              )}

              {/* Full catalyst + headwinds (expanded only) */}
              {analysis.catalyst && (
                <div className="text-sm space-y-1.5">
                  <p className="text-content-secondary leading-relaxed">
                    <span className="text-blue-400 font-medium">Catalyst: </span>{analysis.catalyst}
                  </p>
                  {analysis.headwinds && (
                    <p className="text-content-secondary leading-relaxed">
                      <span className="text-content-faint font-medium">Headwinds: </span>{analysis.headwinds}
                    </p>
                  )}
                </div>
              )}

              {/* Data Gaps */}
              {dataGaps.length > 0 && (
                <details className="text-sm">
                  <summary className="text-content-faint cursor-pointer hover:text-content-muted">
                    Data Gaps ({dataGaps.length})
                  </summary>
                  <div className="mt-1.5 space-y-0.5 pl-3">
                    {dataGaps.map((gap: string, i: number) => (
                      <p key={i} className="text-content-faint">- {gap}</p>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}

          {/* Legacy reason/risk (for old signals without structured analysis) */}
          {!analysis.catalyst && signal.reason && (
            <div className="text-sm space-y-1">
              <p className="text-content-secondary leading-relaxed">
                <span className="text-content-faint font-medium">Why: </span>{signal.reason}
              </p>
              {signal.risk && (
                <p className="text-content-secondary leading-relaxed">
                  <span className="text-content-faint font-medium">Risk: </span>{signal.risk}
                </p>
              )}
            </div>
          )}

          {/* News */}
          {signal.news?.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-medium text-content-faint">Recent News</div>
              {signal.news.map((n: any, i: number) => (
                <div key={i} className="text-sm text-content-secondary flex gap-2">
                  <span className={`shrink-0 ${n.sentiment === 'POSITIVE' ? 'text-green-400' : n.sentiment === 'NEGATIVE' ? 'text-red-400' : 'text-content-faint'}`}>
                    {n.sentiment === 'POSITIVE' ? '\u25cf' : n.sentiment === 'NEGATIVE' ? '\u25cf' : '\u25cb'}
                  </span>
                  {n.link ? (
                    <a href={n.link} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="hover:text-blue-400 transition underline decoration-content-ghost/30 hover:decoration-blue-400">{n.title}</a>
                  ) : (
                    <span>{n.title}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="text-xs text-content-faint text-right">
            {new Date(signal.signaled_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-secondary/60 rounded-lg p-2.5 text-center">
      <div className="text-content-faint text-xs">{label}</div>
      <div className="text-content-primary text-sm font-medium">{value}</div>
    </div>
  )
}

function TrendItem({ label, direction }: { label: string; direction?: string }) {
  const arrow = direction === 'up' ? '\u2191' : direction === 'down' ? '\u2193' : '?'
  const color = direction === 'up' ? 'text-green-400' : direction === 'down' ? 'text-red-400' : 'text-content-faint'
  return (
    <span>{label} <span className={color}>{arrow}</span></span>
  )
}
