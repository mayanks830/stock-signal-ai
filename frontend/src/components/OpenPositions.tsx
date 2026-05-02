import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import LastUpdated from './LastUpdated'
import FilterBar from './FilterBar'

export default function OpenPositions() {
  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['open'],
    queryFn: () => fetch('/api/signals/open').then(r => r.json()),
  })

  const [confidence, setConfidence] = useState('All')
  const [outcome, setOutcome] = useState('All')
  const [sector, setSector] = useState('All')

  const sectors = useMemo(() => {
    if (!data?.length) return []
    return [...new Set(data.map((s: any) => s.sector).filter(Boolean))].sort() as string[]
  }, [data])

  const filtered = useMemo(() => {
    if (!data?.length) return []
    return data.filter((s: any) => {
      if (confidence !== 'All') {
        const raw = s.confidence || '5'
        const confNum = raw === 'HIGH' ? 8 : raw === 'MEDIUM' ? 6 : parseInt(raw) || 5
        if (confidence === '7+' && confNum < 7) return false
        if (confidence === '5+' && confNum < 5) return false
        if (confidence === '<5' && confNum >= 5) return false
      }
      if (sector !== 'All' && s.sector !== sector) return false
      return true
    })
  }, [data, confidence, sector])

  if (isLoading) return <div className="text-content-muted text-sm py-8 text-center">Loading...</div>
  if (!data?.length) return <div className="text-content-faint text-sm py-8 text-center">No open positions.</div>

  return (
    <div>
      <LastUpdated timestamp={dataUpdatedAt} />
      <FilterBar
        confidence={confidence} onConfidence={setConfidence}
        outcome={outcome} onOutcome={setOutcome}
        sector={sector} onSector={setSector}
        sectors={sectors}
        hideOutcome
      />
      {filtered.length === 0 ? (
        <div className="text-content-faint text-sm py-8 text-center">No positions match the selected filters.</div>
      ) : (
        <div className="space-y-3">
          {filtered.map((s: any) => {
            const pct = s.pct_change ?? 0
            const isPos = pct >= 0
            return (
              <div key={s.id} className="border border-border bg-surface-secondary rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-content-primary">{s.ticker}</span>
                    <span className="text-xs text-content-muted">{s.sector}</span>
                    {s.earnings_within_7d && <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">Earnings Soon</span>}
                  </div>
                  <div className="text-xs text-content-muted mt-1">
                    Entry: ${s.current_price} · Target: ${s.price_target ?? 'N/A'} · Stop: ${s.stop_loss ?? 'N/A'}
                  </div>
                  <div className="text-xs text-content-faint mt-0.5">
                    Signaled: {new Date(s.signaled_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="text-left sm:text-right">
                  <div className={`text-lg font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>
                    {isPos ? '+' : ''}{pct.toFixed(2)}%
                  </div>
                  <div className="text-xs text-content-faint">Current P&L</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
