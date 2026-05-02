import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import SignalCard from './SignalCard'
import LastUpdated from './LastUpdated'
import FilterBar from './FilterBar'

const TYPE_LABELS: Record<string, string> = {
  MOMENTUM: 'Momentum',
  EARLY: 'Early Signal',
  DIP_BUY: 'Buy the Dip',
  PULLBACK: 'Pullback',
  CONGRESS: 'Congress',
}

export default function SignalFeed() {
  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['signals'],
    queryFn: () => fetch('/api/signals?limit=50').then(r => r.json()),
  })

  const [confidence, setConfidence] = useState('All')
  const [outcome, setOutcome] = useState('All')
  const [sector, setSector] = useState('All')
  const [signalType, setSignalType] = useState('All')

  const sectors = useMemo(() => {
    if (!data?.length) return []
    return [...new Set(data.map((s: any) => s.sector).filter(Boolean))].sort() as string[]
  }, [data])

  const signalTypes = useMemo(() => {
    if (!data?.length) return []
    return [...new Set(data.map((s: any) => s.signal_type || 'MOMENTUM').filter(Boolean))].sort() as string[]
  }, [data])

  const filtered = useMemo(() => {
    if (!data?.length) return []
    return data.filter((s: any) => {
      if (confidence !== 'All' && (s.confidence || '').toUpperCase() !== confidence) return false
      if (outcome !== 'All' && (s.outcome || 'OPEN') !== outcome) return false
      if (sector !== 'All' && s.sector !== sector) return false
      if (signalType !== 'All' && (s.signal_type || 'MOMENTUM') !== signalType) return false
      return true
    })
  }, [data, confidence, outcome, sector, signalType])

  if (isLoading) return <div className="text-content-muted text-sm py-8 text-center">Loading signals...</div>
  if (!data?.length) return <div className="text-content-faint text-sm py-8 text-center">No signals yet. Run a scan to get started.</div>

  return (
    <div>
      <LastUpdated timestamp={dataUpdatedAt} />
      {/* Signal type filter */}
      {signalTypes.length > 1 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {['All', ...signalTypes].map(t => (
            <button
              key={t}
              onClick={() => setSignalType(t)}
              className={`px-3 py-1 text-xs rounded-full transition ${
                signalType === t
                  ? 'bg-blue-600 text-white'
                  : 'bg-surface-secondary text-content-faint hover:text-content-secondary'
              }`}
            >
              {t === 'All' ? 'All' : TYPE_LABELS[t] || t}
            </button>
          ))}
        </div>
      )}
      <FilterBar
        confidence={confidence} onConfidence={setConfidence}
        outcome={outcome} onOutcome={setOutcome}
        sector={sector} onSector={setSector}
        sectors={sectors}
      />
      {filtered.length === 0 ? (
        <div className="text-content-faint text-sm py-8 text-center">No signals match the selected filters.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 items-start">
          {filtered.map((signal: any) => <SignalCard key={signal.id} signal={signal} />)}
        </div>
      )}
    </div>
  )
}
