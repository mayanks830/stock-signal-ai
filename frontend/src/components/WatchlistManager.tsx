import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

interface WatchlistItem {
  id: number
  ticker: string
  category: string
  added_at: string
}

export default function WatchlistManager() {
  const [ticker, setTicker] = useState('')
  const [category, setCategory] = useState<'equity' | 'etf'>('equity')
  const queryClient = useQueryClient()

  const { data: items = [], isLoading } = useQuery<WatchlistItem[]>({
    queryKey: ['watchlist'],
    queryFn: () => fetch('/api/watchlist').then(r => r.json()),
  })

  const addMutation = useMutation({
    mutationFn: (item: { ticker: string; category: string }) =>
      fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      setTicker('')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (t: string) =>
      fetch(`/api/watchlist/${encodeURIComponent(t)}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const handleAdd = () => {
    const t = ticker.trim().toUpperCase()
    if (!t) return
    addMutation.mutate({ ticker: t, category })
  }

  const equities = items.filter(i => i.category === 'equity')
  const etfs = items.filter(i => i.category === 'etf')

  if (isLoading) return <div className="text-content-muted text-sm py-8 text-center">Loading watchlist...</div>

  return (
    <div className="space-y-6">
      {/* Add row */}
      <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
        <input
          type="text"
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
          placeholder="Ticker (e.g. AAPL)"
          className="bg-surface-secondary border border-border-subtle rounded-lg px-4 py-2.5 text-content-primary placeholder-content-faint focus:outline-none focus:border-blue-500 text-sm w-full sm:w-40"
        />
        <select
          value={category}
          onChange={e => setCategory(e.target.value as 'equity' | 'etf')}
          className="bg-surface-secondary border border-border-subtle rounded-lg px-3 py-2.5 text-content-primary text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="equity">Equity</option>
          <option value="etf">ETF</option>
        </select>
        <button
          onClick={handleAdd}
          disabled={!ticker.trim() || addMutation.isPending}
          className="bg-blue-600 hover:bg-blue-500 disabled:bg-surface-tertiary disabled:text-content-faint text-white text-sm px-5 py-2.5 rounded-lg transition font-medium"
        >
          Add
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TickerList
          title={`Equities (${equities.length})`}
          items={equities}
          onDelete={t => deleteMutation.mutate(t)}
          deleting={deleteMutation.isPending}
        />
        <TickerList
          title={`ETFs (${etfs.length})`}
          items={etfs}
          onDelete={t => deleteMutation.mutate(t)}
          deleting={deleteMutation.isPending}
        />
      </div>
    </div>
  )
}

function TickerList({
  title,
  items,
  onDelete,
  deleting,
}: {
  title: string
  items: WatchlistItem[]
  onDelete: (ticker: string) => void
  deleting: boolean
}) {
  return (
    <div className="border border-border bg-surface-secondary rounded-xl p-4">
      <h3 className="text-sm font-semibold text-content-muted uppercase tracking-wide mb-3">{title}</h3>
      {items.length === 0 ? (
        <div className="text-content-faint text-xs">No items</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {items.map(item => (
            <span
              key={item.ticker}
              className="inline-flex items-center gap-1.5 bg-surface-tertiary text-content-primary text-sm px-3 py-1.5 rounded-lg"
            >
              {item.ticker}
              <button
                onClick={() => onDelete(item.ticker)}
                disabled={deleting}
                className="text-content-faint hover:text-red-400 transition text-xs ml-1"
                title="Remove"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
