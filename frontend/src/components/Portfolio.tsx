import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import LastUpdated from './LastUpdated'
import FilterBar from './FilterBar'

type SortKey = 'ticker' | 'sector' | 'confidence' | 'signaled_at' | 'entry_price' | 'exit_price' | 'pct_change' | 'outcome'
type View = 'positions' | 'history'

export default function Portfolio() {
  const [view, setView] = useState<View>('positions')

  const { data: openData, isLoading: openLoading, dataUpdatedAt } = useQuery({
    queryKey: ['open'],
    queryFn: () => fetch('/api/signals/open').then(r => r.json()),
  })

  const { data: perfData, isLoading: perfLoading } = useQuery({
    queryKey: ['performance'],
    queryFn: () => fetch('/api/performance').then(r => r.json()),
  })

  const [confidence, setConfidence] = useState('All')
  const [outcome, setOutcome] = useState('All')
  const [sector, setSector] = useState('All')

  const sectors = useMemo(() => {
    const all = [...(openData || []), ...(perfData || [])]
    if (!all.length) return []
    return [...new Set(all.map((s: any) => s.sector).filter(Boolean))].sort() as string[]
  }, [openData, perfData])

  const filteredOpen = useMemo(() => {
    if (!openData?.length) return []
    return openData.filter((s: any) => {
      if (confidence !== 'All' && (s.confidence || '').toUpperCase() !== confidence) return false
      if (sector !== 'All' && s.sector !== sector) return false
      return true
    })
  }, [openData, confidence, sector])

  // Portfolio summary stats
  const summary = useMemo(() => {
    const positions = openData || []
    const perf = perfData || []
    const totalOpen = positions.length
    const avgPnl = positions.length > 0
      ? positions.reduce((sum: number, s: any) => sum + (s.pct_change ?? 0), 0) / positions.length
      : 0
    const wins = perf.filter((r: any) => r.outcome === 'WIN').length
    const losses = perf.filter((r: any) => r.outcome === 'LOSS').length
    return { totalOpen, avgPnl, wins, losses, totalClosed: perf.length }
  }, [openData, perfData])

  // Performance table sort
  const [sortKey, setSortKey] = useState<SortKey>('signaled_at')
  const [sortAsc, setSortAsc] = useState(false)

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(key === 'ticker' || key === 'sector') }
  }

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortAsc ? ' \u25b2' : ' \u25bc') : ''

  const sortedPerf = useMemo(() => {
    if (!perfData?.length) return []
    return [...perfData].sort((a: any, b: any) => {
      let av = a[sortKey], bv = b[sortKey]
      if (sortKey === 'signaled_at') { av = av || ''; bv = bv || '' }
      if (sortKey === 'confidence') {
        const rank: Record<string, number> = { HIGH: 2, MEDIUM: 1 }
        av = rank[av] ?? 0; bv = rank[bv] ?? 0
      }
      if (sortKey === 'outcome') {
        const rank: Record<string, number> = { WIN: 3, LOSS: 2, OPEN: 1 }
        av = rank[av || 'OPEN'] ?? 0; bv = rank[bv || 'OPEN'] ?? 0
      }
      if (av == null) return 1
      if (bv == null) return -1
      if (av < bv) return sortAsc ? -1 : 1
      if (av > bv) return sortAsc ? 1 : -1
      return 0
    })
  }, [perfData, sortKey, sortAsc])

  const columns: { key: SortKey; label: string; align: string }[] = [
    { key: 'ticker', label: 'Ticker', align: 'text-left' },
    { key: 'sector', label: 'Sector', align: 'text-left' },
    { key: 'confidence', label: 'Confidence', align: 'text-left' },
    { key: 'signaled_at', label: 'Signal Date', align: 'text-left' },
    { key: 'entry_price', label: 'Entry', align: 'text-right' },
    { key: 'exit_price', label: 'Exit', align: 'text-right' },
    { key: 'pct_change', label: 'P&L', align: 'text-right' },
    { key: 'outcome', label: 'Outcome', align: 'text-center' },
  ]

  if (openLoading && perfLoading) return <div className="text-content-muted text-sm py-8 text-center">Loading...</div>

  return (
    <div>
      <LastUpdated timestamp={dataUpdatedAt} />

      {/* Portfolio Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <SummaryCard label="Open Positions" value={summary.totalOpen} accent="text-blue-400" />
        <SummaryCard
          label="Avg Open P&L"
          value={`${summary.avgPnl >= 0 ? '+' : ''}${summary.avgPnl.toFixed(2)}%`}
          accent={summary.avgPnl >= 0 ? 'text-green-400' : 'text-red-400'}
        />
        <SummaryCard label="Closed Trades" value={summary.totalClosed} accent="text-content-primary" />
        <SummaryCard
          label="Win / Loss"
          value={`${summary.wins} / ${summary.losses}`}
          accent={summary.wins >= summary.losses ? 'text-green-400' : 'text-red-400'}
        />
      </div>

      {/* View toggle */}
      <div className="flex items-center gap-1 mb-4 bg-surface-secondary rounded-lg p-1 w-fit">
        <button
          onClick={() => setView('positions')}
          className={`px-4 py-1.5 rounded-md text-xs font-medium transition ${
            view === 'positions' ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary'
          }`}
        >
          Open Positions{summary.totalOpen > 0 && ` (${summary.totalOpen})`}
        </button>
        <button
          onClick={() => setView('history')}
          className={`px-4 py-1.5 rounded-md text-xs font-medium transition ${
            view === 'history' ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary'
          }`}
        >
          History{summary.totalClosed > 0 && ` (${summary.totalClosed})`}
        </button>
      </div>

      {/* Open Positions view */}
      {view === 'positions' && (
        <>
          <FilterBar
            confidence={confidence} onConfidence={setConfidence}
            outcome={outcome} onOutcome={setOutcome}
            sector={sector} onSector={setSector}
            sectors={sectors}
            hideOutcome
          />
          {!openData?.length ? (
            <div className="border border-border-subtle border-dashed rounded-xl py-10 text-center">
              <div className="text-3xl mb-2 opacity-30">&#x1F4C8;</div>
              <div className="text-content-faint text-sm">No open positions yet</div>
              <div className="text-content-ghost text-xs mt-1">Run a scan to generate signals</div>
            </div>
          ) : filteredOpen.length === 0 ? (
            <div className="text-content-faint text-sm py-8 text-center">No positions match the selected filters.</div>
          ) : (
            <div className="space-y-3">
              {filteredOpen.map((s: any) => {
                const pct = s.pct_change ?? 0
                const isPos = pct >= 0
                const borderAccent = isPos ? 'border-l-green-500' : 'border-l-red-500'
                return (
                  <div key={s.id} className={`border border-border border-l-[3px] ${borderAccent} bg-surface-secondary rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-content-primary text-base">{s.ticker}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          (s.confidence || '').toUpperCase() === 'HIGH' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'
                        }`}>{(s.confidence || 'MEDIUM').toUpperCase()}</span>
                        <span className="text-xs text-content-muted">{s.sector}</span>
                        {s.earnings_within_7d && <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">Earnings Soon</span>}
                      </div>
                      <div className="flex gap-4 mt-1.5 text-xs">
                        <span className="text-content-muted">Entry <span className="text-content-secondary font-medium">${s.current_price}</span></span>
                        <span className="text-content-muted">Target <span className="text-green-400 font-medium">${s.price_target ?? 'N/A'}</span></span>
                        <span className="text-content-muted">Stop <span className="text-red-400 font-medium">${s.stop_loss ?? 'N/A'}</span></span>
                      </div>
                      <div className="text-xs text-content-faint mt-1">
                        {new Date(s.signaled_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="text-left sm:text-right flex-shrink-0">
                      <div className={`text-xl font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>
                        {isPos ? '+' : ''}{pct.toFixed(2)}%
                      </div>
                      <div className={`text-[10px] font-medium uppercase tracking-wider ${isPos ? 'text-green-500/60' : 'text-red-500/60'}`}>
                        {isPos ? 'Winning' : 'Losing'}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {/* Performance History view */}
      {view === 'history' && (
        <>
          {!perfData?.length ? (
            <div className="border border-border-subtle border-dashed rounded-xl py-10 text-center">
              <div className="text-3xl mb-2 opacity-30">&#x1F4CA;</div>
              <div className="text-content-faint text-sm">No completed trades yet</div>
              <div className="text-content-ghost text-xs mt-1">Closed positions will be tracked here</div>
            </div>
          ) : (
            <div className="overflow-x-auto border border-border rounded-xl">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-content-muted text-xs border-b border-border bg-surface-secondary/50">
                    {columns.map(col => (
                      <th
                        key={col.key}
                        className={`${col.align} py-3 px-4 cursor-pointer select-none hover:text-content-primary transition font-medium`}
                        onClick={() => toggleSort(col.key)}
                      >
                        {col.label}{sortIcon(col.key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedPerf.map((r: any, i: number) => {
                    const pct = r.pct_change
                    const oc = r.outcome || 'OPEN'
                    return (
                      <tr key={i} className="border-b border-border/30 hover:bg-surface-secondary/50 transition">
                        <td className="py-3 px-4 font-semibold text-content-primary">{r.ticker}</td>
                        <td className="py-3 px-4 text-content-muted">{r.sector}</td>
                        <td className="py-3 px-4">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${r.confidence === 'HIGH' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                            {r.confidence}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-content-muted">{r.signaled_at ? new Date(r.signaled_at).toLocaleDateString() : '\u2014'}</td>
                        <td className="py-3 px-4 text-right text-content-secondary">${r.entry_price}</td>
                        <td className="py-3 px-4 text-right text-content-secondary">{r.exit_price ? `$${r.exit_price}` : '\u2014'}</td>
                        <td className={`py-3 px-4 text-right font-semibold ${pct == null ? 'text-content-faint' : pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '\u2014'}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            oc === 'WIN' ? 'bg-green-500/20 text-green-400' :
                            oc === 'LOSS' ? 'bg-red-500/20 text-red-400' :
                            'bg-surface-tertiary text-content-muted'
                          }`}>
                            {oc}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function SummaryCard({ label, value, accent }: { label: string; value: string | number; accent: string }) {
  return (
    <div className="bg-surface-secondary border border-border rounded-xl p-3">
      <div className="text-xs text-content-faint mb-1">{label}</div>
      <div className={`text-lg font-bold ${accent}`}>{value}</div>
    </div>
  )
}
