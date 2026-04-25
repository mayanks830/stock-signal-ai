import { useState, useEffect, useRef } from 'react'
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts'

interface PriceData {
  current_price: number
  daily_change_pct: number
  wow_change_pct: number
  volume_ratio: number
  range_position: number
  trend_1d: string
  trend_1w: string
  trend_1m: string
  price_history?: { date: string; close: number }[]
}

interface Technicals {
  rsi: number | null
  rsi_status: string | null
  ma50: number | null
  ma200: number | null
  above_50ma: boolean | null
  above_200ma: boolean | null
  ma_cross: string | null
  macd: { macd: number; signal: number; histogram: number; crossover: string } | null
  trailing_returns: Record<string, number>
}

interface NewsItem {
  title: string
  date: string
  link?: string
  sentiment?: string
}

interface Social {
  insider_buys: number
  insider_sells: number
  insider_signal: string
  insider_trades: any[]
  st_sentiment: string
  st_bullish: number
  st_bearish: number
  st_volume: number
  cong_buys: number
  cong_sells: number
  cong_signal: string
  cong_trades: { filer: string; party: string; action: string; tx_date: string }[]
}

interface AiAnalysis {
  outlook: string
  signal: string
  reasoning: string
  price_target?: number | null
  stop_loss?: number | null
  risk?: string
  key_levels?: { support: number; resistance: number }
}

interface SearchResult {
  ticker: string
  price_data: PriceData
  technicals: Technicals | null
  news: NewsItem[]
  social: Social
  market_context: { vix: number | null; vix_label: string; spy_wow_pct: number | null }
  ai_analysis: AiAnalysis
  cached?: boolean
}

const trendArrow = (t: string) => t === 'up' ? '↑' : '↓'
const trendColor = (t: string) => t === 'up' ? 'text-green-400' : 'text-red-400'
const pctColor = (v: number) => v >= 0 ? 'text-green-400' : 'text-red-400'
const pctSign = (v: number) => v >= 0 ? `+${v.toFixed(2)}%` : `${v.toFixed(2)}%`

const outlookColors: Record<string, string> = {
  BULLISH: 'bg-green-500/20 text-green-400 border-green-500/30',
  BEARISH: 'bg-red-500/20 text-red-400 border-red-500/30',
  NEUTRAL: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
}
const signalColors: Record<string, string> = {
  BUY: 'bg-green-600 text-white',
  SELL: 'bg-red-600 text-white',
  HOLD: 'bg-gray-600 text-gray-200',
}
const sentimentColors: Record<string, string> = {
  POSITIVE: 'text-green-400',
  NEGATIVE: 'text-red-400',
  NEUTRAL: 'text-content-muted',
}

function getTickerFromHash(): string {
  const parts = window.location.hash.slice(1).split('/')
  if (parts[0]?.toLowerCase() === 'search' && parts[1]) {
    return parts[1].toUpperCase()
  }
  return ''
}

export default function StockSearch() {
  const [ticker, setTicker] = useState(getTickerFromHash)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [error, setError] = useState('')
  const didAutoSearch = useRef(false)

  const analyze = async (t?: string) => {
    const symbol = (t || ticker).trim().toUpperCase()
    if (!symbol) return
    setTicker(symbol)
    setLoading(true)
    setError('')
    setResult(null)
    window.location.hash = `search/${symbol}`
    try {
      const resp = await fetch(`/api/search?ticker=${encodeURIComponent(symbol)}`)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(err.detail || `HTTP ${resp.status}`)
      }
      setResult(await resp.json())
    } catch (e: any) {
      setError(e.message || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  // Auto-search if ticker was in the URL hash on mount
  useEffect(() => {
    if (didAutoSearch.current) return
    const hashTicker = getTickerFromHash()
    if (hashTicker) {
      didAutoSearch.current = true
      analyze(hashTicker)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
        <input
          type="text"
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && analyze()}
          placeholder="Enter ticker (e.g. AAPL)"
          className="w-full sm:flex-1 sm:max-w-xs bg-surface-secondary border border-border-subtle rounded-lg px-4 py-2.5 text-content-primary placeholder-content-faint focus:outline-none focus:border-blue-500 text-sm"
        />
        <button
          onClick={() => analyze()}
          disabled={loading || !ticker.trim()}
          className="bg-blue-600 hover:bg-blue-500 disabled:bg-surface-tertiary disabled:text-content-faint text-white text-sm px-6 py-2.5 rounded-lg transition font-medium"
        >
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
        {result?.cached && (
          <span className="text-xs text-content-faint">cached</span>
        )}
      </div>

      {loading && (
        <div className="text-content-muted text-sm py-12 text-center">
          <div className="text-2xl mb-3 animate-pulse">&#x1f50d;</div>
          Fetching price data, technicals, news, social data, and running AI analysis...
          <br />
          <span className="text-content-faint text-xs">This may take 10-15 seconds</span>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {result && <ResultDisplay result={result} />}
    </div>
  )
}

const RANGES = ['1mo', '3mo', '6mo', '1y', '2y', '5y'] as const
const RANGE_LABELS: Record<string, string> = {
  '1mo': '1M', '3mo': '3M', '6mo': '6M', '1y': '1Y', '2y': '2Y', '5y': '5Y',
}

function PriceChart({ data, ticker }: { data: { date: string; close: number }[]; ticker: string }) {
  const [range, setRange] = useState<string>('1mo')
  const [chartData, setChartData] = useState(data)
  const [loading, setLoading] = useState(false)

  const fetchRange = async (r: string) => {
    if (r === '1mo') {
      setRange(r)
      setChartData(data)
      return
    }
    setRange(r)
    setLoading(true)
    try {
      const resp = await fetch(`/api/price-history?ticker=${encodeURIComponent(ticker)}&range=${r}`)
      if (resp.ok) {
        const result = await resp.json()
        setChartData(result.price_history || [])
      }
    } catch { /* keep current data */ }
    setLoading(false)
  }

  const displayData = chartData.length >= 2 ? chartData : data
  if (!displayData || displayData.length < 2) return null

  const isUp = displayData[displayData.length - 1].close >= displayData[0].close
  const color = isUp ? '#4ade80' : '#f87171'

  return (
    <div className="border border-border bg-surface-secondary rounded-xl p-4">
      <div className="flex items-center justify-between mb-3 gap-2">
        <h3 className="text-sm font-semibold text-content-muted uppercase tracking-wide whitespace-nowrap">Price History</h3>
        <div className="flex flex-wrap gap-1">
          {RANGES.map(r => (
            <button
              key={r}
              onClick={() => fetchRange(r)}
              className={`px-2 py-0.5 text-xs rounded transition ${
                range === r
                  ? 'bg-blue-600 text-white'
                  : 'text-content-faint hover:text-content-secondary hover:bg-surface-hover'
              }`}
            >
              {RANGE_LABELS[r]}
            </button>
          ))}
        </div>
      </div>
      <div className="h-48 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface-secondary/50 z-10">
            <span className="text-content-muted text-xs animate-pulse">Loading...</span>
          </div>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={displayData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border-subtle))" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: 'rgb(var(--color-text-faint))' }}
              tickFormatter={(v: string) => v.slice(5)}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 10, fill: 'rgb(var(--color-text-faint))' }}
              domain={['auto', 'auto']}
              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
              width={50}
            />
            <Tooltip
              contentStyle={{ backgroundColor: 'rgb(var(--color-bg-secondary))', border: '1px solid rgb(var(--color-border-subtle))', borderRadius: '8px', fontSize: '12px' }}
              labelStyle={{ color: 'rgb(var(--color-text-muted))' }}
              formatter={(value) => [`$${Number(value).toFixed(2)}`, 'Close']}
            />
            <Line
              type="monotone"
              dataKey="close"
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: color }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function ResultDisplay({ result }: { result: SearchResult }) {
  const { price_data: p, technicals: tech, news, social, ai_analysis: ai, market_context: mkt } = result

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 flex-wrap">
        <h2 className="text-2xl font-bold text-content-primary">{result.ticker}</h2>
        <span className="text-2xl font-bold text-content-primary">${p.current_price}</span>
        <span className={`text-sm font-medium ${pctColor(p.daily_change_pct)}`}>
          {pctSign(p.daily_change_pct)} today
        </span>
        <span className={`text-xs px-3 py-1 rounded-full border ${outlookColors[ai.outlook] || outlookColors.NEUTRAL}`}>
          {ai.outlook}
        </span>
        <span className={`text-xs px-3 py-1 rounded-full font-bold ${signalColors[ai.signal] || signalColors.HOLD}`}>
          {ai.signal}
        </span>
      </div>

      <div className="flex gap-4 text-xs text-content-faint">
        <span>VIX: {mkt.vix ?? 'N/A'} ({mkt.vix_label})</span>
        <span>SPY WoW: {mkt.spy_wow_pct != null ? pctSign(mkt.spy_wow_pct) : 'N/A'}</span>
      </div>

      {p.price_history && p.price_history.length > 0 && (
        <PriceChart data={p.price_history} ticker={result.ticker} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title="Price Overview">
          <Row label="Daily Change" value={pctSign(p.daily_change_pct)} color={pctColor(p.daily_change_pct)} />
          <Row label="Weekly Change" value={pctSign(p.wow_change_pct)} color={pctColor(p.wow_change_pct)} />
          <Row label="Volume Ratio" value={`${p.volume_ratio}x avg`} color={p.volume_ratio >= 1.5 ? 'text-yellow-400' : 'text-content-secondary'} />
          <Row label="30d Range Position" value={`${p.range_position}%`} />
          <div className="flex gap-4 mt-2 text-sm">
            <span>1d <span className={trendColor(p.trend_1d)}>{trendArrow(p.trend_1d)}</span></span>
            <span>1w <span className={trendColor(p.trend_1w)}>{trendArrow(p.trend_1w)}</span></span>
            <span>1m <span className={trendColor(p.trend_1m)}>{trendArrow(p.trend_1m)}</span></span>
          </div>
        </Section>

        <Section title="Technicals">
          {tech ? (
            <>
              {tech.rsi != null && (
                <Row
                  label="RSI (14)"
                  value={`${tech.rsi.toFixed(1)} — ${tech.rsi_status}`}
                  color={tech.rsi_status === 'OVERBOUGHT' ? 'text-red-400' : tech.rsi_status === 'OVERSOLD' ? 'text-green-400' : 'text-content-secondary'}
                />
              )}
              {tech.ma50 != null && (
                <Row label="50-day MA" value={`$${tech.ma50} (${tech.above_50ma ? 'above' : 'below'})`} color={tech.above_50ma ? 'text-green-400' : 'text-red-400'} />
              )}
              {tech.ma200 != null && (
                <Row label="200-day MA" value={`$${tech.ma200} (${tech.above_200ma ? 'above' : 'below'})`} color={tech.above_200ma ? 'text-green-400' : 'text-red-400'} />
              )}
              {tech.ma_cross && <Row label="MA Cross" value={tech.ma_cross} color={tech.ma_cross === 'GOLDEN' ? 'text-green-400' : 'text-red-400'} />}
              {tech.macd && <Row label="MACD" value={tech.macd.crossover} color={tech.macd.crossover === 'BULLISH_CROSS' ? 'text-green-400' : tech.macd.crossover === 'BEARISH_CROSS' ? 'text-red-400' : 'text-content-secondary'} />}
              {tech.trailing_returns && Object.keys(tech.trailing_returns).length > 0 && (
                <div className="flex gap-3 mt-2 text-xs">
                  {Object.entries(tech.trailing_returns).map(([k, v]) => (
                    <span key={k} className="text-content-muted">{k}: <span className={pctColor(v)}>{pctSign(v)}</span></span>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="text-content-faint text-xs">Technical data unavailable</div>
          )}
        </Section>

        <Section title={`News (${news.length})`}>
          {news.length > 0 ? (
            <div className="space-y-2">
              {news.map((n, i) => (
                <div key={i} className="text-xs">
                  <span className={`font-medium ${sentimentColors[n.sentiment || 'NEUTRAL'] || 'text-content-muted'}`}>
                    [{n.sentiment || 'NEUTRAL'}]
                  </span>{' '}
                  {n.link ? (
                    <a href={n.link} target="_blank" rel="noopener noreferrer" className="text-content-secondary hover:text-blue-400 transition underline decoration-content-ghost/30 hover:decoration-blue-400">{n.title}</a>
                  ) : (
                    <span className="text-content-secondary">{n.title}</span>
                  )}
                  <span className="text-content-ghost ml-2">{n.date}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-content-faint text-xs">No recent news</div>
          )}
        </Section>

        <Section title="Social & Insider">
          <Row
            label="Insider Activity"
            value={social.insider_signal === 'NONE' ? 'No activity' : `${social.insider_signal} (${social.insider_buys}B / ${social.insider_sells}S)`}
            color={social.insider_signal.includes('BUY') ? 'text-green-400' : social.insider_signal.includes('SELL') ? 'text-red-400' : 'text-content-secondary'}
          />
          <Row
            label="StockTwits"
            value={social.st_sentiment === 'UNKNOWN' ? 'No data' : `${social.st_sentiment} (${social.st_bullish}/${social.st_bearish})`}
            color={social.st_sentiment?.includes('BULLISH') ? 'text-green-400' : social.st_sentiment?.includes('BEARISH') ? 'text-red-400' : 'text-content-secondary'}
          />
          <Row
            label="Congress"
            value={social.cong_signal === 'NONE' ? 'No activity' : `${social.cong_signal} (${social.cong_buys}B / ${social.cong_sells}S)`}
            color={social.cong_signal?.includes('BUY') ? 'text-green-400' : social.cong_signal?.includes('SELL') ? 'text-red-400' : 'text-content-secondary'}
          />
          {social.cong_trades?.length > 0 && (
            <div className="mt-1 space-y-0.5">
              {social.cong_trades.slice(0, 3).map((t, i) => (
                <div key={i} className="text-xs text-content-faint">
                  {t.filer} <span className={t.party === 'D' ? 'text-blue-400' : t.party === 'R' ? 'text-red-400' : ''}>({t.party})</span>{' '}
                  <span className={t.action === 'BUY' ? 'text-green-400' : 'text-red-400'}>{t.action}</span>{' '}
                  {t.tx_date}
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>

      {/* AI Analysis */}
      <div className="border border-border bg-surface-secondary rounded-xl p-5">
        <h3 className="text-sm font-semibold text-content-muted uppercase tracking-wide mb-3">AI Analysis</h3>
        <p className="text-content-secondary text-sm leading-relaxed mb-4">{ai.reasoning}</p>
        <div className="flex flex-wrap gap-4 text-sm">
          {ai.price_target != null && (
            <span className="text-content-muted">Target: <span className="text-green-400 font-medium">${ai.price_target}</span></span>
          )}
          {ai.stop_loss != null && (
            <span className="text-content-muted">Stop Loss: <span className="text-red-400 font-medium">${ai.stop_loss}</span></span>
          )}
          {ai.key_levels && (
            <>
              <span className="text-content-muted">Support: <span className="text-blue-400">${ai.key_levels.support}</span></span>
              <span className="text-content-muted">Resistance: <span className="text-blue-400">${ai.key_levels.resistance}</span></span>
            </>
          )}
        </div>
        {ai.risk && (
          <p className="text-xs text-content-faint mt-3">Risk: {ai.risk}</p>
        )}
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border bg-surface-secondary rounded-xl p-4">
      <h3 className="text-sm font-semibold text-content-muted uppercase tracking-wide mb-3">{title}</h3>
      {children}
    </div>
  )
}

function Row({ label, value, color = 'text-content-secondary' }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between text-sm py-1">
      <span className="text-content-faint">{label}</span>
      <span className={color}>{value}</span>
    </div>
  )
}
