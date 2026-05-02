import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AreaChart, Area, ReferenceLine, ResponsiveContainer, Tooltip } from 'recharts'

const CONF_COLOR: Record<string, string> = {
  HIGH: 'border-green-500 bg-green-500/10',
  MEDIUM: 'border-yellow-500 bg-yellow-500/10',
}
const CONF_BADGE: Record<string, string> = {
  HIGH: 'bg-green-500/20 text-green-400',
  MEDIUM: 'bg-yellow-500/20 text-yellow-400',
}
const TREND_ARROW: Record<string, string> = { up: '\u2191', down: '\u2193' }

const SIGNAL_TYPE_BADGE: Record<string, { label: string; color: string }> = {
  MOMENTUM: { label: 'Momentum', color: 'bg-green-500/20 text-green-400' },
  EARLY: { label: 'Early Signal', color: 'bg-blue-500/20 text-blue-400' },
  DIP_BUY: { label: 'Buy the Dip', color: 'bg-orange-500/20 text-orange-400' },
  PULLBACK: { label: 'Pullback', color: 'bg-purple-500/20 text-purple-400' },
  CONGRESS: { label: 'Congress', color: 'bg-yellow-500/20 text-yellow-400' },
}

// Score breakdown factor logic
type FactorStatus = 'pass' | 'partial' | 'fail'
interface Factor { label: string; status: FactorStatus; detail: string }

function computeFactors(signal: any): Factor[] {
  const factors: Factor[] = []

  // News Catalyst
  const news = signal.news || []
  const posCount = news.filter((n: any) => n.sentiment === 'POSITIVE').length
  const negCount = news.filter((n: any) => n.sentiment === 'NEGATIVE').length
  if (news.length === 0) {
    factors.push({ label: 'News Catalyst', status: 'fail', detail: 'No articles' })
  } else if (posCount > negCount) {
    factors.push({ label: 'News Catalyst', status: 'pass', detail: `${news.length} articles, ${posCount} positive` })
  } else {
    factors.push({ label: 'News Catalyst', status: 'partial', detail: `${news.length} articles, mixed` })
  }

  // Volume Surge
  const vr = signal.volume_ratio
  if (vr == null) {
    factors.push({ label: 'Volume Surge', status: 'fail', detail: 'N/A' })
  } else if (vr >= 1.5) {
    factors.push({ label: 'Volume Surge', status: 'pass', detail: `${vr}x average` })
  } else if (vr >= 1.0) {
    factors.push({ label: 'Volume Surge', status: 'partial', detail: `${vr}x average` })
  } else {
    factors.push({ label: 'Volume Surge', status: 'fail', detail: `${vr}x average` })
  }

  // Trend Momentum
  const trends = [signal.trend_1d, signal.trend_1w, signal.trend_1m]
  const upCount = trends.filter(t => t === 'up').length
  if (upCount === 3) {
    factors.push({ label: 'Trend Momentum', status: 'pass', detail: '3/3 periods up' })
  } else if (upCount === 2) {
    factors.push({ label: 'Trend Momentum', status: 'partial', detail: '2/3 periods up' })
  } else {
    factors.push({ label: 'Trend Momentum', status: 'fail', detail: `${upCount}/3 periods up` })
  }

  // Relative Strength
  const rs = signal.relative_strength_vs_spy
  if (rs == null) {
    factors.push({ label: 'Relative Strength', status: 'fail', detail: 'N/A' })
  } else if (rs > 2) {
    factors.push({ label: 'Relative Strength', status: 'pass', detail: `+${rs.toFixed(1)}% vs SPY` })
  } else if (rs >= 0) {
    factors.push({ label: 'Relative Strength', status: 'partial', detail: `+${rs.toFixed(1)}% vs SPY` })
  } else {
    factors.push({ label: 'Relative Strength', status: 'fail', detail: `${rs.toFixed(1)}% vs SPY` })
  }

  return factors
}

const FACTOR_ICON: Record<FactorStatus, { icon: string; color: string }> = {
  pass: { icon: '\u2713', color: 'text-green-400' },
  partial: { icon: '~', color: 'text-yellow-400' },
  fail: { icon: '\u2717', color: 'text-red-400' },
}

export default function SignalCard({ signal }: { signal: any }) {
  const [expanded, setExpanded] = useState(false)
  const conf = (signal.confidence || 'MEDIUM').toUpperCase()

  const { data: priceData } = useQuery({
    queryKey: ['prices', signal.id],
    queryFn: () => fetch(`/api/signals/${signal.id}/prices`).then(r => r.json()),
    enabled: expanded,
  })

  const entryPrice = signal.current_price
  const targetPrice = signal.price_target
  const stopPrice = signal.stop_loss

  // Compute action box values
  const upsidePct = targetPrice && entryPrice
    ? ((targetPrice - entryPrice) / entryPrice * 100).toFixed(1)
    : null
  const downsidePct = stopPrice && entryPrice
    ? ((stopPrice - entryPrice) / entryPrice * 100).toFixed(1)
    : null
  const riskReward = targetPrice && stopPrice && entryPrice && stopPrice !== entryPrice
    ? Math.abs((targetPrice - entryPrice) / (entryPrice - stopPrice)).toFixed(1)
    : null

  // Chart color: green if latest price >= entry, red otherwise
  const latestPrice = priceData?.prices?.length > 0
    ? priceData.prices[priceData.prices.length - 1].price
    : null
  const isWinning = latestPrice != null ? latestPrice >= entryPrice : true
  const chartColor = isWinning ? '#22c55e' : '#ef4444'

  return (
    <div
      className={`border rounded-xl p-4 cursor-pointer transition hover:border-opacity-80 ${CONF_COLOR[conf] || 'border-border-subtle bg-surface-secondary'}`}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-content-primary">{signal.ticker}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CONF_BADGE[conf]}`}>{conf}</span>
            {signal.signal_type && signal.signal_type !== 'MOMENTUM' && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SIGNAL_TYPE_BADGE[signal.signal_type]?.color || 'bg-gray-500/20 text-gray-400'}`}>
                {SIGNAL_TYPE_BADGE[signal.signal_type]?.label || signal.signal_type}
              </span>
            )}
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

      {/* Action Box — always visible */}
      {targetPrice && stopPrice && (
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-bold text-blue-400">ACTION: BUY</span>
            {riskReward && (
              <span className={`text-xs font-semibold ${
                parseFloat(riskReward) >= 2 ? 'text-green-400' : parseFloat(riskReward) >= 1 ? 'text-yellow-400' : 'text-red-400'
              }`}>R:R {riskReward}:1</span>
            )}
          </div>
          <div className="text-sm text-content-primary font-medium">
            Entry ${entryPrice} → Target ${targetPrice} {upsidePct && <span className="text-green-400">(+{upsidePct}%)</span>}
          </div>
          <div className="text-xs text-content-muted">
            Stop ${stopPrice} {downsidePct && <span className="text-red-400">({downsidePct}%)</span>}
          </div>
        </div>
      )}

      {/* Structured Analysis or fallback to reason/risk */}
      {signal.analysis ? (
        <div className="text-xs space-y-1.5">
          <p className="text-content-secondary leading-relaxed">
            <span className="text-blue-400 font-medium">Catalyst: </span>{signal.analysis.catalyst}
          </p>
          <p className="text-red-400/80 leading-relaxed">
            <span className="font-medium">Risk: </span>{signal.analysis.headwinds}
          </p>
        </div>
      ) : (
        <div className="text-xs space-y-1">
          <p className="text-content-secondary leading-relaxed"><span className="text-content-faint font-medium">Why: </span>{signal.reason}</p>
          {signal.risk && (
            <p className="text-red-400/80 leading-relaxed"><span className="font-medium">Risk: </span>{signal.risk}</p>
          )}
        </div>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-border-subtle space-y-3">
          {/* Improved Chart — AreaChart with gradient */}
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

          {/* Structured Analysis Framework */}
          {signal.analysis ? (
            <div className="space-y-2">
              <div className="bg-surface-secondary/60 rounded-lg p-3">
                <div className="text-xs font-medium text-content-faint mb-2">Company Profile</div>
                <div className="space-y-1.5 text-xs">
                  <AnalysisRow label="Business" value={signal.analysis.business_model} />
                  <AnalysisRow label="Financials" value={signal.analysis.financial_health} />
                  <AnalysisRow label="Moat" value={signal.analysis.competitive_position} />
                  <AnalysisRow label="Valuation" value={signal.analysis.valuation} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="bg-green-500/8 border border-green-500/15 rounded-lg p-3">
                  <div className="text-xs font-medium text-green-400 mb-1">Bull Case</div>
                  <p className="text-xs text-content-secondary leading-relaxed">{signal.analysis.bull_case}</p>
                </div>
                <div className="bg-red-500/8 border border-red-500/15 rounded-lg p-3">
                  <div className="text-xs font-medium text-red-400 mb-1">Bear Case</div>
                  <p className="text-xs text-content-secondary leading-relaxed">{signal.analysis.bear_case}</p>
                </div>
              </div>

              {signal.analysis.recommendation && (
                <div className="bg-blue-500/8 border border-blue-500/15 rounded-lg p-2.5">
                  <p className="text-xs text-blue-300 leading-relaxed">{signal.analysis.recommendation}</p>
                </div>
              )}

              {/* Technical factors */}
              <div className="bg-surface-secondary/60 rounded-lg p-3">
                <div className="text-xs font-medium text-content-faint mb-2">Signal Factors</div>
                <div className="space-y-1.5">
                  {computeFactors(signal).map(f => (
                    <div key={f.label} className="flex items-center gap-2 text-xs">
                      <span className={`font-bold w-3 text-center ${FACTOR_ICON[f.status].color}`}>{FACTOR_ICON[f.status].icon}</span>
                      <span className="text-content-secondary w-28">{f.label}</span>
                      <span className="text-content-muted">{f.detail}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* Fallback: old-style score breakdown */
            <div className="bg-surface-secondary/60 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-content-faint">Signal Score Breakdown</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CONF_BADGE[conf]}`}>{conf}</span>
              </div>
              <div className="space-y-1.5">
                {computeFactors(signal).map(f => (
                  <div key={f.label} className="flex items-center gap-2 text-xs">
                    <span className={`font-bold w-3 text-center ${FACTOR_ICON[f.status].color}`}>{FACTOR_ICON[f.status].icon}</span>
                    <span className="text-content-secondary w-28">{f.label}</span>
                    <span className="text-content-muted">{f.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

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
