import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AreaChart, Area, ReferenceLine, ResponsiveContainer, Tooltip } from 'recharts'

const TREND_ARROW: Record<string, string> = { up: '\u2191', down: '\u2193' }

const SIGNAL_TYPE_BADGE: Record<string, { label: string; color: string }> = {
  MOMENTUM: { label: 'Momentum', color: 'bg-green-500/20 text-green-400' },
  EARLY: { label: 'Early Signal', color: 'bg-blue-500/20 text-blue-400' },
  DIP_BUY: { label: 'Buy the Dip', color: 'bg-orange-500/20 text-orange-400' },
  PULLBACK: { label: 'Pullback', color: 'bg-purple-500/20 text-purple-400' },
  CONGRESS: { label: 'Congress', color: 'bg-yellow-500/20 text-yellow-400' },
}

// Signal action badge colors
const SIGNAL_BADGE: Record<string, { label: string; color: string; border: string }> = {
  BUY: { label: 'BUY', color: 'bg-green-500/20 text-green-400', border: 'border-green-500' },
  SELL: { label: 'SELL', color: 'bg-red-500/20 text-red-400', border: 'border-red-500' },
  HOLD: { label: 'HOLD', color: 'bg-gray-500/20 text-gray-400', border: 'border-gray-500' },
  CONFLICTED: { label: 'CONFLICTED', color: 'bg-orange-500/20 text-orange-400', border: 'border-orange-500' },
}

function getConfidenceBg(conf: number): string {
  if (conf >= 8) return 'bg-green-500/20 text-green-400'
  if (conf >= 6) return 'bg-yellow-500/20 text-yellow-400'
  if (conf >= 4) return 'bg-orange-500/20 text-orange-400'
  return 'bg-red-500/20 text-red-400'
}

function getCardBorder(signal: string, conf: number): string {
  if (signal === 'CONFLICTED') return 'border-orange-500 bg-orange-500/5'
  if (signal === 'SELL') return 'border-red-500 bg-red-500/5'
  if (conf >= 7) return 'border-green-500 bg-green-500/10'
  if (conf >= 5) return 'border-yellow-500 bg-yellow-500/10'
  return 'border-border-subtle bg-surface-secondary'
}

export default function SignalCard({ signal }: { signal: any }) {
  const [expanded, setExpanded] = useState(false)

  // Parse confidence: handle both "HIGH"/"MEDIUM" (legacy) and "1"-"10" (new)
  const rawConf = signal.confidence || '5'
  const confNum = rawConf === 'HIGH' ? 8 : rawConf === 'MEDIUM' ? 6 : parseInt(rawConf) || 5
  const signalAction = signal.signal || 'BUY'
  const signalBadge = SIGNAL_BADGE[signalAction] || SIGNAL_BADGE.HOLD

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

  const latestPrice = priceData?.prices?.length > 0
    ? priceData.prices[priceData.prices.length - 1].price
    : null
  const isWinning = latestPrice != null ? latestPrice >= entryPrice : true
  const chartColor = isWinning ? '#22c55e' : '#ef4444'

  const analysis = signal.analysis || {}
  const conflicts = analysis.conflicts || []
  const dataGaps = analysis.data_gaps || []

  return (
    <div
      className={`border rounded-xl p-4 cursor-pointer transition hover:border-opacity-80 ${getCardBorder(signalAction, confNum)}`}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-lg font-bold text-content-primary">{signal.ticker}</span>
            {/* Signal action badge */}
            <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${signalBadge.color}`}>
              {signalBadge.label}
            </span>
            {/* Confidence */}
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getConfidenceBg(confNum)}`}>
              {confNum}/10
            </span>
            {/* Signal type */}
            {signal.signal_type && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SIGNAL_TYPE_BADGE[signal.signal_type]?.color || 'bg-gray-500/20 text-gray-400'}`}>
                {SIGNAL_TYPE_BADGE[signal.signal_type]?.label || signal.signal_type}
              </span>
            )}
            {/* Outcome */}
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              signal.outcome === 'WIN' ? 'bg-green-500/20 text-green-400' :
              signal.outcome === 'LOSS' ? 'bg-red-500/20 text-red-400' :
              'bg-blue-500/15 text-blue-400'
            }`}>{signal.outcome === 'WIN' ? 'WIN' : signal.outcome === 'LOSS' ? 'LOSS' : 'OPEN'}</span>
            {signal.earnings_within_7d && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">Earnings</span>
            )}
          </div>
          <div className="text-xs text-content-muted mt-0.5">{signal.name} · {signal.sector}</div>
        </div>
        <div className="text-right">
          <div className="text-content-primary font-semibold">${entryPrice}</div>
          <div className={`text-sm font-medium ${signal.wow_change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {signal.wow_change_pct >= 0 ? '\u2191' : '\u2193'} {Math.abs(signal.wow_change_pct).toFixed(2)}% WoW
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
      <div className="flex gap-3 text-xs text-content-muted mb-3">
        <span>1d <span className={signal.trend_1d === 'up' ? 'text-green-400' : 'text-red-400'}>{TREND_ARROW[signal.trend_1d] || '?'}</span></span>
        <span>1w <span className={signal.trend_1w === 'up' ? 'text-green-400' : 'text-red-400'}>{TREND_ARROW[signal.trend_1w] || '?'}</span></span>
        <span>1m <span className={signal.trend_1m === 'up' ? 'text-green-400' : 'text-red-400'}>{TREND_ARROW[signal.trend_1m] || '?'}</span></span>
      </div>

      {/* Conflicts warning */}
      {conflicts.length > 0 && (
        <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-2.5 mb-3">
          <div className="text-xs font-bold text-orange-400 mb-1">Conflicts</div>
          {conflicts.map((c: string, i: number) => (
            <p key={i} className="text-xs text-orange-300/80 leading-relaxed">- {c}</p>
          ))}
        </div>
      )}

      {/* Action Box */}
      {targetPrice && stopPrice && (
        <div className={`${
          signalAction === 'SELL' ? 'bg-red-500/10 border-red-500/20' :
          signalAction === 'CONFLICTED' ? 'bg-orange-500/10 border-orange-500/20' :
          'bg-blue-500/10 border-blue-500/20'
        } border rounded-lg p-3 mb-3`}>
          <div className="flex items-center justify-between mb-1">
            <span className={`text-xs font-bold ${
              signalAction === 'SELL' ? 'text-red-400' :
              signalAction === 'CONFLICTED' ? 'text-orange-400' :
              'text-blue-400'
            }`}>ACTION: {signalAction}</span>
            {riskReward && (
              <span className="text-xs text-content-muted">
                Risk ${Math.abs(entryPrice - stopPrice).toFixed(0)} to make ${Math.abs(targetPrice - entryPrice).toFixed(0)}
              </span>
            )}
          </div>
          <div className="text-sm text-content-primary font-medium">
            Entry ${entryPrice} {'\u2192'} Target ${targetPrice} {upsidePct && <span className="text-green-400">(+{upsidePct}%)</span>}
          </div>
          <div className="text-xs text-content-muted">
            Stop ${stopPrice} {downsidePct && <span className="text-red-400">({downsidePct}%)</span>}
          </div>
        </div>
      )}

      {/* Catalyst + Risk summary */}
      {analysis.catalyst ? (
        <div className="text-xs space-y-1.5">
          <p className="text-content-secondary leading-relaxed">
            <span className="text-blue-400 font-medium">Catalyst: </span>{analysis.catalyst}
          </p>
          <p className="text-red-400/80 leading-relaxed">
            <span className="font-medium">Risk: </span>{analysis.headwinds}
          </p>
        </div>
      ) : signal.reason ? (
        <div className="text-xs space-y-1">
          <p className="text-content-secondary leading-relaxed"><span className="text-content-faint font-medium">Why: </span>{signal.reason}</p>
          {signal.risk && (
            <p className="text-red-400/80 leading-relaxed"><span className="font-medium">Risk: </span>{signal.risk}</p>
          )}
        </div>
      ) : null}

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-border-subtle space-y-3">
          {/* Chart */}
          {priceData?.prices?.length > 0 && (
            <div className="h-[120px]">
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
                    label={{ value: `Entry $${entryPrice}`, position: 'right', fill: '#9ca3af', fontSize: 10 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'rgb(var(--color-bg-secondary))', border: '1px solid rgb(var(--color-border-subtle))', fontSize: '11px' }}
                    formatter={(v: any) => [`$${v}`, 'Price']}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Structured Analysis */}
          {analysis.business_model || analysis.bull_case ? (
            <div className="space-y-2">
              {/* Company Profile */}
              {(analysis.business_model || analysis.valuation) && (
                <div className="bg-surface-secondary/60 rounded-lg p-3">
                  <div className="text-xs font-medium text-content-faint mb-2">Company Profile</div>
                  <div className="space-y-1.5 text-xs">
                    <AnalysisRow label="Business" value={analysis.business_model} />
                    <AnalysisRow label="Valuation" value={analysis.valuation} />
                  </div>
                </div>
              )}

              {/* Technicals & Sentiment */}
              {(analysis.technicals?.summary || analysis.sentiment?.summary) && (
                <div className="grid grid-cols-2 gap-2">
                  {analysis.technicals?.summary && (
                    <div className="bg-surface-secondary/60 rounded-lg p-3">
                      <div className="text-xs font-medium text-content-faint mb-1">Technicals</div>
                      <p className="text-xs text-content-secondary leading-relaxed">{analysis.technicals.summary}</p>
                      {analysis.technicals.indicators?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {analysis.technicals.indicators.map((ind: string, i: number) => (
                            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-surface-secondary text-content-muted">{ind}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {analysis.sentiment?.summary && (
                    <div className="bg-surface-secondary/60 rounded-lg p-3">
                      <div className="text-xs font-medium text-content-faint mb-1">Sentiment</div>
                      <p className="text-xs text-content-secondary leading-relaxed">{analysis.sentiment.summary}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Bull / Bear cases */}
              {(analysis.bull_case || analysis.bear_case) && (
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-green-500/8 border border-green-500/15 rounded-lg p-3">
                    <div className="text-xs font-medium text-green-400 mb-1">Bull Case</div>
                    <p className="text-xs text-content-secondary leading-relaxed">{analysis.bull_case}</p>
                  </div>
                  <div className="bg-red-500/8 border border-red-500/15 rounded-lg p-3">
                    <div className="text-xs font-medium text-red-400 mb-1">Bear Case</div>
                    <p className="text-xs text-content-secondary leading-relaxed">{analysis.bear_case}</p>
                  </div>
                </div>
              )}

              {/* Invalidation + Upcoming Events */}
              {(analysis.invalidation || analysis.upcoming_events?.length > 0) && (
                <div className="bg-surface-secondary/60 rounded-lg p-3 space-y-1.5">
                  {analysis.invalidation && (
                    <div className="text-xs">
                      <span className="text-red-400 font-medium">Invalidation: </span>
                      <span className="text-content-secondary">{analysis.invalidation}</span>
                    </div>
                  )}
                  {analysis.upcoming_events?.length > 0 && (
                    <div className="text-xs">
                      <span className="text-yellow-400 font-medium">Upcoming: </span>
                      <span className="text-content-secondary">{analysis.upcoming_events.join(' | ')}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Recommendation */}
              {analysis.recommendation && (
                <div className="bg-blue-500/8 border border-blue-500/15 rounded-lg p-2.5">
                  <p className="text-xs text-blue-300 leading-relaxed">{analysis.recommendation}</p>
                </div>
              )}

              {/* Data Gaps */}
              {dataGaps.length > 0 && (
                <details className="text-xs">
                  <summary className="text-content-faint cursor-pointer hover:text-content-muted">
                    Data Gaps ({dataGaps.length})
                  </summary>
                  <div className="mt-1.5 space-y-0.5 pl-3">
                    {dataGaps.map((gap: string, i: number) => (
                      <p key={i} className="text-content-ghost">- {gap}</p>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ) : null}

          {/* News */}
          {signal.news?.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs text-content-faint font-medium">Recent News</div>
              {signal.news.map((n: any, i: number) => (
                <div key={i} className="text-xs text-content-secondary flex gap-2">
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

          <div className="text-xs text-content-ghost text-right">
            {new Date(signal.signaled_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-secondary/60 rounded-lg p-2 text-center">
      <div className="text-content-faint text-xs">{label}</div>
      <div className="text-content-primary text-xs font-medium">{value}</div>
    </div>
  )
}

function AnalysisRow({ label, value }: { label: string; value?: string }) {
  if (!value) return null
  return (
    <div className="flex gap-2">
      <span className="text-content-faint font-medium w-16 shrink-0">{label}</span>
      <span className="text-content-secondary leading-relaxed">{value}</span>
    </div>
  )
}
