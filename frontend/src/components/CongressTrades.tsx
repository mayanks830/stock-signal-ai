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

type SortKey = 'tx_date' | 'filer' | 'ticker' | 'action' | 'party' | 'chamber' | 'amount' | 'reporting_gap'

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

  // Top tickers by trade count
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

  // Most active filers
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
      {/* Buy / Sell */}
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

      {/* Party Breakdown */}
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

      {/* Top Tickers */}
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

      {/* Most Active Filers */}
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

export default function CongressTrades() {
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

  // Apply filters
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
    if (sortKey === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortKey(key)
      setSortAsc(false)
    }
  }

  const sortIcon = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortAsc ? ' ↑' : ' ↓'
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
          {hasActiveFilters ? `${filtered.length} / ${trades.length}` : trades.length} trades
        </span>
      </div>

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
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
