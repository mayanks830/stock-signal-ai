import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import LastUpdated from './LastUpdated'

interface Trade {
  filer: string
  party: string
  chamber: string
  ticker: string
  company: string
  action: string
  amount: string
  tx_date: string
  pub_date: string
  reporting_gap: number | null
  owner: string
}

interface LeaderboardEntry {
  filer: string
  party: string
  chamber: string
  trade_count: number
  avg_return_pct: number
  best_ticker: string | null
  best_return_pct: number | null
  total_value: number | null
}

interface SenatorTrade {
  ticker: string
  tx_date: string
  amount: string
  value_numeric: number | null
  price_at_trade: number | null
  price_current: number | null
  return_pct: number | null
}

type SortKey = 'tx_date' | 'filer' | 'ticker' | 'action' | 'party' | 'chamber' | 'amount' | 'reporting_gap'
type View = 'trades' | 'rankings'

const partyBadge = (p: string) => {
  if (p === 'D') return 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
  if (p === 'R') return 'bg-red-500/20 text-red-400 border border-red-500/30'
  return 'bg-surface-tertiary text-content-muted border border-border-subtle'
}

const actionColor = (a: string) => {
  if (a === 'BUY') return 'text-green-400'
  if (a === 'SELL') return 'text-red-400'
  return 'text-content-muted'
}

function parseAmount(s: string): number {
  const n = Number(s.replace(/[$,]/g, ''))
  return isNaN(n) ? 0 : n
}

function formatUsd(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

function Summary({ trades }: { trades: Trade[] }) {
  if (trades.length === 0) return null

  const buys = trades.filter(t => t.action === 'BUY')
  const sells = trades.filter(t => t.action === 'SELL')
  const dems = trades.filter(t => t.party === 'D')
  const reps = trades.filter(t => t.party === 'R')
  const buyVol = buys.reduce((s, t) => s + parseAmount(t.amount), 0)
  const sellVol = sells.reduce((s, t) => s + parseAmount(t.amount), 0)

  const tickerCounts: Record<string, { buys: number; sells: number }> = {}
  for (const t of trades) {
    const key = t.ticker || t.company.slice(0, 20)
    if (!key) continue
    if (!tickerCounts[key]) tickerCounts[key] = { buys: 0, sells: 0 }
    if (t.action === 'BUY') tickerCounts[key].buys++
    else if (t.action === 'SELL') tickerCounts[key].sells++
  }
  const topTickers = Object.entries(tickerCounts)
    .sort((a, b) => (b[1].buys + b[1].sells) - (a[1].buys + a[1].sells))
    .slice(0, 5)

  const filerCounts: Record<string, number> = {}
  for (const t of trades) {
    filerCounts[t.filer] = (filerCounts[t.filer] || 0) + 1
  }
  const topFilers = Object.entries(filerCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  const buyPct = trades.length ? Math.round((buys.length / trades.length) * 100) : 0

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <div className="border border-border bg-surface-secondary rounded-xl p-3">
        <div className="text-xs text-content-faint uppercase tracking-wide mb-2">Buy / Sell</div>
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-lg font-bold text-green-400">{buys.length}</span>
          <span className="text-content-ghost">/</span>
          <span className="text-lg font-bold text-red-400">{sells.length}</span>
        </div>
        <div className="w-full bg-surface-tertiary rounded-full h-1.5">
          <div className="bg-green-500 h-1.5 rounded-full" style={{ width: `${buyPct}%` }} />
        </div>
        <div className="flex justify-between text-xs text-content-ghost mt-1">
          <span>{formatUsd(buyVol)} bought</span>
          <span>{formatUsd(sellVol)} sold</span>
        </div>
      </div>

      <div className="border border-border bg-surface-secondary rounded-xl p-3">
        <div className="text-xs text-content-faint uppercase tracking-wide mb-2">By Party</div>
        <div className="flex items-baseline gap-3 mb-2">
          <span className="text-blue-400 font-bold">{dems.length} <span className="text-xs font-normal">D</span></span>
          <span className="text-red-400 font-bold">{reps.length} <span className="text-xs font-normal">R</span></span>
          {trades.length - dems.length - reps.length > 0 && (
            <span className="text-content-muted font-bold">{trades.length - dems.length - reps.length} <span className="text-xs font-normal">I</span></span>
          )}
        </div>
        <div className="space-y-1 text-xs text-content-faint">
          <div>D: {dems.filter(t => t.action === 'BUY').length}B / {dems.filter(t => t.action === 'SELL').length}S</div>
          <div>R: {reps.filter(t => t.action === 'BUY').length}B / {reps.filter(t => t.action === 'SELL').length}S</div>
        </div>
      </div>

      <div className="border border-border bg-surface-secondary rounded-xl p-3">
        <div className="text-xs text-content-faint uppercase tracking-wide mb-2">Top Tickers</div>
        <div className="space-y-1">
          {topTickers.map(([ticker, { buys: b, sells: s }]) => (
            <div key={ticker} className="flex justify-between text-xs">
              <span className="text-blue-400 font-mono truncate max-w-[80px]">{ticker}</span>
              <span>
                <span className="text-green-400">{b}B</span>
                <span className="text-content-ghost mx-1">/</span>
                <span className="text-red-400">{s}S</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="border border-border bg-surface-secondary rounded-xl p-3">
        <div className="text-xs text-content-faint uppercase tracking-wide mb-2">Most Active</div>
        <div className="space-y-1">
          {topFilers.map(([filer, count]) => (
            <div key={filer} className="flex justify-between text-xs">
              <span className="text-content-secondary truncate max-w-[120px]">{filer}</span>
              <span className="text-content-muted">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const ASSET_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'stock', label: 'Stock' },
  { value: 'stock-options', label: 'Stock Options' },
  { value: 'etf', label: 'ETF' },
  { value: 'mutual-fund', label: 'Mutual Fund' },
  { value: 'crypto', label: 'Crypto' },
  { value: 'corporate-bond', label: 'Corporate Bond' },
  { value: 'reit', label: 'REIT' },
  { value: 'other-securities', label: 'Other Securities' },
] as const

// ── Senator Rankings View ────────────────────────────────────────────────────

function SenatorRankings() {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [partyFilter, setPartyFilter] = useState<'All' | 'D' | 'R'>('All')
  const [chamberFilter, setChamberFilter] = useState<'All' | 'Senate' | 'House'>('All')
  const [minTrades, setMinTrades] = useState(1)

  const { data: leaderboard, isLoading } = useQuery({
    queryKey: ['congress-leaderboard'],
    queryFn: () => fetch('/api/congress/leaderboard').then(r => r.json()),
  })

  const { data: senatorData } = useQuery({
    queryKey: ['congress-senator', expanded],
    queryFn: () => fetch(`/api/congress/senator/${encodeURIComponent(expanded!)}`).then(r => r.json()),
    enabled: !!expanded,
  })

  if (isLoading) return <div className="text-content-muted text-sm py-8 text-center">Loading senator rankings...</div>

  const allEntries: LeaderboardEntry[] = leaderboard || []

  const entries = allEntries.filter(e => {
    if (partyFilter !== 'All' && e.party !== partyFilter) return false
    if (chamberFilter !== 'All' && e.chamber !== chamberFilter) return false
    if (e.trade_count < minTrades) return false
    return true
  })

  if (allEntries.length === 0) {
    return (
      <div className="border border-border-subtle border-dashed rounded-xl py-10 text-center">
        <div className="text-3xl mb-2 opacity-30">&#x1F3DB;&#xFE0F;</div>
        <div className="text-content-faint text-sm">No senator performance data yet</div>
        <div className="text-content-ghost text-xs mt-1">Data is collected daily from congressional trade filings</div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Methodology note */}
      <div className="bg-surface-secondary/50 border border-border-subtle rounded-lg px-4 py-3">
        <div className="text-xs text-content-muted leading-relaxed">
          Ranked by <span className="text-content-secondary font-medium">average return on stock purchases</span> &mdash; comparing the stock price on the trade date to today's price. Only BUY trades with available price data are included. Prices updated daily.
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-0.5">
          {(['All', 'D', 'R'] as const).map(p => (
            <button
              key={p}
              onClick={() => setPartyFilter(p)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                partyFilter === p ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary'
              }`}
            >
              {p === 'All' ? 'All Parties' : p === 'D' ? 'Democrat' : 'Republican'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-0.5">
          {(['All', 'Senate', 'House'] as const).map(c => (
            <button
              key={c}
              onClick={() => setChamberFilter(c)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                chamberFilter === c ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary'
              }`}
            >
              {c === 'All' ? 'Both Chambers' : c}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-content-faint">Min trades:</label>
          <select
            value={minTrades}
            onChange={e => setMinTrades(Number(e.target.value))}
            className="bg-surface-secondary border border-border-subtle rounded-lg px-2 py-1 text-xs text-content-primary focus:outline-none focus:border-blue-500"
          >
            <option value={1}>1+</option>
            <option value={2}>2+</option>
            <option value={3}>3+</option>
            <option value={5}>5+</option>
          </select>
        </div>
        <span className="text-xs text-content-ghost ml-auto">{entries.length} of {allEntries.length} members</span>
      </div>

      {entries.length === 0 ? (
        <div className="text-content-faint text-sm text-center py-8">No members match the selected filters</div>
      ) : (
      <div className="border border-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-content-muted text-xs border-b border-border bg-surface-secondary/50">
              <th className="py-3 px-4 text-left font-medium w-8">#</th>
              <th className="py-3 px-4 text-left font-medium">Member</th>
              <th className="py-3 px-4 text-center font-medium">Party</th>
              <th className="py-3 px-4 text-right font-medium">Buys</th>
              <th className="py-3 px-4 text-right font-medium" title="Average return from trade date to today">Avg Return</th>
              <th className="py-3 px-4 text-left font-medium">Best Pick</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => {
              const isExpanded = expanded === e.filer
              const trades: SenatorTrade[] = isExpanded ? (senatorData?.trades || []) : []
              return (
                <tr key={e.filer} className="contents">
                  <td colSpan={6} className="p-0">
                    <div
                      className={`grid grid-cols-[2rem_1fr_4rem_4rem_5rem_8rem] items-center border-b border-border/30 cursor-pointer transition ${
                        isExpanded ? 'bg-surface-secondary' : 'hover:bg-surface-secondary/50'
                      }`}
                      onClick={() => setExpanded(isExpanded ? null : e.filer)}
                    >
                      <div className="py-3 px-4 text-content-faint text-xs">{i + 1}</div>
                      <div className="py-3 px-4">
                        <div className="text-content-primary font-medium">{e.filer}</div>
                        <div className="text-xs text-content-faint">{e.chamber}</div>
                      </div>
                      <div className="py-3 px-4 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${partyBadge(e.party)}`}>{e.party}</span>
                      </div>
                      <div className="py-3 px-4 text-right text-content-muted">{e.trade_count}</div>
                      <div className={`py-3 px-4 text-right font-bold ${
                        e.avg_return_pct >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {e.avg_return_pct >= 0 ? '+' : ''}{e.avg_return_pct}%
                      </div>
                      <div className="py-3 px-4">
                        {e.best_ticker && (
                          <span className="text-xs">
                            <span className="text-blue-400 font-mono">{e.best_ticker}</span>
                            <span className="text-green-400 ml-1">+{e.best_return_pct?.toFixed(1)}%</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Expanded trade details */}
                    {isExpanded && trades.length > 0 && (
                      <div className="bg-surface-primary border-b border-border/30 px-4 py-3">
                        <div className="text-xs text-content-faint uppercase tracking-wide mb-2">Buy Trades</div>
                        <div className="space-y-1.5">
                          {trades.map((t, ti) => (
                            <div key={ti} className="flex items-center gap-3 text-xs bg-surface-secondary/50 rounded-lg px-3 py-2">
                              <span className="text-blue-400 font-mono font-medium w-14">{t.ticker}</span>
                              <span className="text-content-muted w-20">{t.tx_date}</span>
                              <span className="text-content-faint w-20">{t.amount}</span>
                              {t.price_at_trade != null && (
                                <span className="text-content-muted">
                                  Entry ${t.price_at_trade}
                                </span>
                              )}
                              {t.price_current != null && (
                                <span className="text-content-muted">
                                  Now ${t.price_current}
                                </span>
                              )}
                              {t.return_pct != null ? (
                                <span className={`font-semibold ml-auto ${t.return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                  {t.return_pct >= 0 ? '+' : ''}{t.return_pct.toFixed(1)}%
                                </span>
                              ) : (
                                <span className="text-content-ghost ml-auto">Pending</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                  )}
                  {isExpanded && trades.length === 0 && senatorData && (
                    <div className="bg-surface-primary border-b border-border/30 px-4 py-3 text-xs text-content-faint text-center">
                      No priced trades yet for this senator
                    </div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
      )}
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────

function getInitialView(): View {
  const hash = window.location.hash
  if (hash.includes('/rankings')) return 'rankings'
  return 'trades'
}

export default function CongressTrades() {
  const [view, setView] = useState<View>(getInitialView)
  const [sortKey, setSortKey] = useState<SortKey>('tx_date')
  const [sortAsc, setSortAsc] = useState(false)
  const [nameFilter, setNameFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [assetType, setAssetType] = useState('')

  const { data, isLoading, isError, error, dataUpdatedAt, refetch } = useQuery({
    queryKey: ['congress', assetType],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: '200' })
      if (assetType) params.set('assetType', assetType)
      const r = await fetch(`/api/congress?${params}`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    },
    refetchInterval: 600_000,
    retry: 2,
  })

  const trades: Trade[] = data?.trades ?? []

  const filtered = trades.filter(t => {
    if (nameFilter) {
      const q = nameFilter.toLowerCase()
      const matchesName = t.filer.toLowerCase().includes(q)
      const matchesTicker = t.ticker.toLowerCase().includes(q)
      const matchesCompany = t.company.toLowerCase().includes(q)
      if (!matchesName && !matchesTicker && !matchesCompany) return false
    }
    if (dateFrom && t.tx_date < dateFrom) return false
    if (dateTo && t.tx_date > dateTo) return false
    return true
  })

  const sorted = [...filtered].sort((a, b) => {
    let av: any = a[sortKey]
    let bv: any = b[sortKey]
    if (sortKey === 'reporting_gap') {
      av = av ?? 999
      bv = bv ?? 999
    }
    if (av < bv) return sortAsc ? -1 : 1
    if (av > bv) return sortAsc ? 1 : -1
    return 0
  })

  const hasActiveFilters = nameFilter || dateFrom || dateTo || assetType

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(false) }
  }

  const sortIcon = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortAsc ? ' \u2191' : ' \u2193'
  }

  if (isLoading) {
    return <div className="text-content-muted text-sm py-12 text-center animate-pulse">Loading congressional trades...</div>
  }

  if (isError) {
    return (
      <div className="text-center py-12 space-y-3">
        <div className="text-red-400 text-sm">Failed to load congressional trades</div>
        <div className="text-content-faint text-xs">{(error as Error)?.message}</div>
        <button
          onClick={() => refetch()}
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs px-4 py-1.5 rounded-lg transition"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <LastUpdated timestamp={dataUpdatedAt} />
        <span className="text-xs text-content-faint">
          {view === 'trades' && (hasActiveFilters ? `${filtered.length} / ${trades.length}` : trades.length)} {view === 'trades' ? 'trades' : ''}
        </span>
      </div>

      {/* View toggle */}
      <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-1 w-fit">
        <button
          onClick={() => { setView('trades'); window.location.hash = 'congress' }}
          className={`px-4 py-1.5 rounded-md text-xs font-medium transition ${
            view === 'trades' ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary'
          }`}
        >
          Recent Trades
        </button>
        <button
          onClick={() => { setView('rankings'); window.location.hash = 'congress/rankings' }}
          className={`px-4 py-1.5 rounded-md text-xs font-medium transition ${
            view === 'rankings' ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary'
          }`}
        >
          Senator Rankings
        </button>
      </div>

      {view === 'rankings' ? (
        <SenatorRankings />
      ) : (
        <>
          {/* Filters */}
          <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 sm:gap-3 items-end">
            <div className="col-span-2 sm:col-span-1">
              <label className="block text-xs text-content-faint mb-1">Name / Ticker</label>
              <input
                type="text"
                value={nameFilter}
                onChange={e => setNameFilter(e.target.value)}
                placeholder="e.g. Pelosi or AAPL"
                className="bg-surface-secondary border border-border-subtle rounded-lg px-3 py-1.5 text-sm text-content-primary placeholder-content-ghost focus:outline-none focus:border-blue-500 w-full sm:w-48"
              />
            </div>
            <div>
              <label className="block text-xs text-content-faint mb-1">From</label>
              <input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                className="bg-surface-secondary border border-border-subtle rounded-lg px-3 py-1.5 text-sm text-content-primary focus:outline-none focus:border-blue-500 w-full"
              />
            </div>
            <div>
              <label className="block text-xs text-content-faint mb-1">To</label>
              <input
                type="date"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
                className="bg-surface-secondary border border-border-subtle rounded-lg px-3 py-1.5 text-sm text-content-primary focus:outline-none focus:border-blue-500 w-full"
              />
            </div>
            <div className="col-span-2 sm:col-span-1">
              <label className="block text-xs text-content-faint mb-1">Asset Type</label>
              <select
                value={assetType}
                onChange={e => setAssetType(e.target.value)}
                className="bg-surface-secondary border border-border-subtle rounded-lg px-3 py-1.5 text-sm text-content-primary focus:outline-none focus:border-blue-500 w-full sm:min-w-[140px]"
              >
                {ASSET_TYPES.map(t => (
                  <option key={t.value} value={t.value} className="bg-surface-secondary text-content-primary">{t.label}</option>
                ))}
              </select>
            </div>
            {hasActiveFilters && (
              <button
                onClick={() => { setNameFilter(''); setDateFrom(''); setDateTo(''); setAssetType('') }}
                className="text-xs text-content-faint hover:text-content-primary px-3 py-1.5 rounded-lg border border-border-subtle hover:border-content-faint transition col-span-2 sm:col-span-1"
              >
                Clear
              </button>
            )}
          </div>

          <Summary trades={filtered} />

          {trades.length === 0 ? (
            <div className="text-center py-12 space-y-3">
              <div className="text-content-faint text-sm">No congressional trades found</div>
              <div className="text-content-ghost text-xs">The scraper may not have returned data. Try refreshing.</div>
              <button
                onClick={() => refetch()}
                className="bg-surface-tertiary hover:bg-surface-hover text-content-primary text-xs px-4 py-1.5 rounded-lg transition"
              >
                Refresh
              </button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-content-faint text-sm text-center py-12">No trades match your filters</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-content-faint text-xs uppercase tracking-wider border-b border-border">
                    {([
                      ['tx_date', 'Date'],
                      ['filer', 'Filer'],
                      ['party', 'Party'],
                      ['chamber', 'Chamber'],
                      ['ticker', 'Ticker'],
                      ['action', 'Buy/Sell'],
                      ['amount', 'Amount'],
                      ['reporting_gap', 'Gap (days)'],
                    ] as [SortKey, string][]).map(([key, label]) => (
                      <th
                        key={key}
                        onClick={() => toggleSort(key)}
                        className="px-3 py-2 cursor-pointer hover:text-content-secondary transition select-none"
                      >
                        {label}{sortIcon(key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((t, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-surface-secondary/50 transition">
                      <td className="px-3 py-2 text-content-secondary whitespace-nowrap">{t.tx_date}</td>
                      <td className="px-3 py-2 text-content-primary font-medium">{t.filer}</td>
                      <td className="px-3 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${partyBadge(t.party)}`}>
                          {t.party}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-content-muted">{t.chamber}</td>
                      <td className="px-3 py-2 font-medium">
                        {t.ticker
                          ? <span className="text-blue-400 font-mono">{t.ticker}</span>
                          : <span className="text-content-faint text-xs" title={t.company}>{t.company.length > 20 ? t.company.slice(0, 20) + '...' : t.company}</span>
                        }
                      </td>
                      <td className={`px-3 py-2 font-medium ${actionColor(t.action)}`}>{t.action}</td>
                      <td className="px-3 py-2 text-content-secondary">{t.amount}</td>
                      <td className="px-3 py-2 text-content-muted">
                        {t.reporting_gap != null ? (
                          <span className={t.reporting_gap > 45 ? 'text-yellow-400' : ''}>{t.reporting_gap}d</span>
                        ) : '\u2014'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
