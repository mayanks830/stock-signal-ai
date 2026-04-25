import { useQuery } from '@tanstack/react-query'
import SignalCard from './SignalCard'
import LastUpdated from './LastUpdated'

export default function SignalFeed() {
  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['signals'],
    queryFn: () => fetch('/api/signals?limit=50').then(r => r.json()),
  })

  if (isLoading) return <div className="text-content-muted text-sm py-8 text-center">Loading signals...</div>
  if (!data?.length) return <div className="text-content-faint text-sm py-8 text-center">No signals yet. Run a scan to get started.</div>

  return (
    <div>
      <LastUpdated timestamp={dataUpdatedAt} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.map((signal: any) => <SignalCard key={signal.id} signal={signal} />)}
      </div>
    </div>
  )
}
