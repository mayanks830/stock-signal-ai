import { useQuery } from '@tanstack/react-query'

export default function PerformanceTable() {
  const { data, isLoading } = useQuery({
    queryKey: ['performance'],
    queryFn: () => fetch('/api/performance').then(r => r.json()),
  })

  if (isLoading) return <div className="text-gray-400 text-sm py-8 text-center">Loading...</div>
  if (!data?.length) return <div className="text-gray-500 text-sm py-8 text-center">No completed signals yet.</div>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 text-xs border-b border-gray-800">
            <th className="text-left py-3 pr-4">Ticker</th>
            <th className="text-left py-3 pr-4">Sector</th>
            <th className="text-left py-3 pr-4">Confidence</th>
            <th className="text-left py-3 pr-4">Signal Date</th>
            <th className="text-right py-3 pr-4">Entry</th>
            <th className="text-right py-3 pr-4">Exit</th>
            <th className="text-right py-3 pr-4">P&L</th>
            <th className="text-center py-3">Outcome</th>
          </tr>
        </thead>
        <tbody>
          {data.map((r: any, i: number) => {
            const pct = r.pct_change
            const outcome = r.outcome || 'OPEN'
            return (
              <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-900 transition">
                <td className="py-3 pr-4 font-semibold text-white">{r.ticker}</td>
                <td className="py-3 pr-4 text-gray-400">{r.sector}</td>
                <td className="py-3 pr-4">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${r.confidence === 'HIGH' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                    {r.confidence}
                  </span>
                </td>
                <td className="py-3 pr-4 text-gray-400">{r.signaled_at ? new Date(r.signaled_at).toLocaleDateString() : '—'}</td>
                <td className="py-3 pr-4 text-right text-gray-300">${r.entry_price}</td>
                <td className="py-3 pr-4 text-right text-gray-300">{r.exit_price ? `$${r.exit_price}` : '—'}</td>
                <td className={`py-3 pr-4 text-right font-semibold ${pct == null ? 'text-gray-500' : pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '—'}
                </td>
                <td className="py-3 text-center">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    outcome === 'WIN' ? 'bg-green-500/20 text-green-400' :
                    outcome === 'LOSS' ? 'bg-red-500/20 text-red-400' :
                    'bg-gray-700 text-gray-400'
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
