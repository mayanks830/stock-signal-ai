import { useQuery } from '@tanstack/react-query'

export default function OpenPositions() {
  const { data, isLoading } = useQuery({
    queryKey: ['open'],
    queryFn: () => fetch('/api/signals/open').then(r => r.json()),
  })

  if (isLoading) return <div className="text-gray-400 text-sm py-8 text-center">Loading...</div>
  if (!data?.length) return <div className="text-gray-500 text-sm py-8 text-center">No open positions.</div>

  return (
    <div className="space-y-3">
      {data.map((s: any) => {
        const pct = s.pct_change ?? 0
        const isPos = pct >= 0
        return (
          <div key={s.id} className="border border-gray-800 bg-gray-900 rounded-xl p-4 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white">{s.ticker}</span>
                <span className="text-xs text-gray-400">{s.sector}</span>
                {s.earnings_within_7d && <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">📅 Earnings Soon</span>}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Entry: ${s.current_price} · Target: ${s.price_target ?? 'N/A'} · Stop: ${s.stop_loss ?? 'N/A'}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                Signaled: {new Date(s.signaled_at).toLocaleDateString()}
              </div>
            </div>
            <div className="text-right">
              <div className={`text-lg font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>
                {isPos ? '+' : ''}{pct.toFixed(2)}%
              </div>
              <div className="text-xs text-gray-500">Current P&L</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
