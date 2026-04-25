import { useState, useEffect } from 'react'

export default function LastUpdated({ timestamp }: { timestamp: number | undefined }) {
  const [, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 5000)
    return () => clearInterval(id)
  }, [])

  if (!timestamp) return null

  const seconds = Math.round((Date.now() - timestamp) / 1000)
  const label = seconds < 60
    ? `${seconds}s ago`
    : seconds < 3600
      ? `${Math.floor(seconds / 60)}m ago`
      : `${Math.floor(seconds / 3600)}h ago`

  return (
    <div className="flex items-center gap-2 text-xs text-content-faint mb-3">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
      </span>
      Last updated {label}
    </div>
  )
}
