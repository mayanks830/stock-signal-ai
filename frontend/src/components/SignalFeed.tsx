import { useQuery } from '@tanstack/react-query'
import SignalCard from './SignalCard'

export default function SignalFeed() {
  const { data, isLoading } = useQuery({
    queryKey: ['signals'],
    queryFn: () => fetch('/api/signals?limit=50').then(r => r.json()),
  })

  if (isLoading) return <div className="text-gray-400 text-sm py-8 text-center">Loading signals...</div>
  if (!data?.length) return <div className="text-gray-500 text-sm py-8 text-center">No signals yet. Run a scan to get started.</div>

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {data.map((signal: any) => <SignalCard key={signal.id} signal={signal} />)}
    </div>
  )
}
