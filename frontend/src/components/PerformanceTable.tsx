import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

type SortKey = 'ticker' | 'sector' | 'confidence' | 'signaled_at' | 'entry_price' | 'exit_price' | 'pct_change' | 'outcome'

export default function PerformanceTable() {
  const { data, isLoading } = useQuery({
    queryKey: ['performance'],
    queryFn: () => fetch('/api/performance').then(r => r.json()),
  })

  const [sortKey, setSortKey] = useState<SortKey>('signaled_at')
  const [sortAsc, setSortAsc] = useState(false)

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(key === 'ticker' || key === 'sector') }
  }

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortAsc ? ' ▲' : ' ▼') : ''

  const sorted = useMemo(() => {
    if (!data?.length) return []
    return [...data].sort((a: any, b: any) => {
      let av = a[sortKey], bv = b[sortKey]
      if (sortKey === 'signaled_at') { av = av || ''; bv = bv || '' }
      if (sortKey === 'confidence') {
        const parseConf = (v: any) => v === 'HIGH' ? 8 : v === 'MEDIUM' ? 6 : parseInt(v) || 5
        av = parseConf(av); bv = parseConf(bv)
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
  }, [data, sortKey, sortAsc])

  if (isLoading) return <div className="text-content-muted text-sm py-8 text-center">Loading...</div>
  if (!data?.length) return <div className="text-content-faint text-sm py-8 text-center">No completed signals yet.</div>

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

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-content-muted text-xs border-b border-border">
            {columns.map(col => (
              <th
                key={col.key}
                className={`${col.align} py-3 ${col.key !== 'outcome' ? 'pr-4' : ''} cursor-pointer select-none hover:text-content-primary transition`}
                onClick={() => toggleSort(col.key)}
              >
                {col.label}{sortIcon(col.key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r: any, i: number) => {
            const pct = r.pct_change
            const outcome = r.outcome || 'OPEN'
            return (
              <tr key={i} className="border-b border-border/50 hover:bg-surface-secondary transition">
                <td className="py-3 pr-4 font-semibold text-content-primary">{r.ticker}</td>
                <td className="py-3 pr-4 text-content-muted">{r.sector}</td>
                <td className="py-3 pr-4">
                  {(() => {
                    const raw = r.confidence || '5'
                    const num = raw === 'HIGH' ? 8 : raw === 'MEDIUM' ? 6 : parseInt(raw) || 5
                    const color = num >= 7 ? 'bg-green-500/20 text-green-400' : num >= 5 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'
                    return <span className={`text-xs px-2 py-0.5 rounded-full ${color}`}>{num}/10</span>
                  })()}
                </td>
                <td className="py-3 pr-4 text-content-muted">{r.signaled_at ? new Date(r.signaled_at).toLocaleDateString() : '—'}</td>
                <td className="py-3 pr-4 text-right text-content-secondary">${r.entry_price}</td>
                <td className="py-3 pr-4 text-right text-content-secondary">{r.exit_price ? `$${r.exit_price}` : '—'}</td>
                <td className={`py-3 pr-4 text-right font-semibold ${pct == null ? 'text-content-faint' : pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '—'}
                </td>
                <td className="py-3 text-center">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    outcome === 'WIN' ? 'bg-green-500/20 text-green-400' :
                    outcome === 'LOSS' ? 'bg-red-500/20 text-red-400' :
                    'bg-surface-tertiary text-content-muted'
                  }`}>
                    {outcome === 'WIN' ? '✅ WIN' : outcome === 'LOSS' ? '❌ LOSS' : '⏳ OPEN'}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
