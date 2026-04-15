import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import SignalFeed from './components/SignalFeed'
import PerformanceTable from './components/PerformanceTable'
import OpenPositions from './components/OpenPositions'
import StatsBar from './components/StatsBar'

const TABS = ['Live Feed', 'Open Positions', 'Performance'] as const
type Tab = typeof TABS[number]

function App() {
  const [tab, setTab] = useState<Tab>('Live Feed')
  const [scanning, setScanning] = useState(false)

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: () => fetch('/api/stats').then(r => r.json()),
  })

  const triggerScan = async () => {
    setScanning(true)
    await fetch('/api/scan/trigger', { method: 'POST' })
    setTimeout(() => setScanning(false), 3000)
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Trading Signals</h1>
          <p className="text-xs text-gray-400">S&P 500 · $1B+ Revenue · AI Analysis</p>
        </div>
        <button
          onClick={triggerScan}
          disabled={scanning}
          className="bg-green-600 hover:bg-green-500 disabled:bg-gray-700 text-white text-sm px-4 py-2 rounded-lg transition"
        >
          {scanning ? '⏳ Scanning...' : '🔍 Run Scan'}
        </button>
      </header>

      <StatsBar stats={stats} />

      <div className="flex gap-1 px-6 py-3 border-b border-gray-800">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === t ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <main className="px-6 py-4">
        {tab === 'Live Feed' && <SignalFeed />}
        {tab === 'Open Positions' && <OpenPositions />}
        {tab === 'Performance' && <PerformanceTable />}
      </main>
    </div>
  )
}

export default App
