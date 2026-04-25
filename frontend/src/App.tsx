import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTheme } from './hooks/useTheme'
import SignalFeed from './components/SignalFeed'
import PerformanceTable from './components/PerformanceTable'
import OpenPositions from './components/OpenPositions'
import ReportsTab from './components/ReportsTab'
import StockSearch from './components/StockSearch'
import WatchlistManager from './components/WatchlistManager'
import CongressTrades from './components/CongressTrades'
import StatsBar from './components/StatsBar'
import ContactForm from './components/ContactForm'

const TABS = ['Signals', 'Positions', 'Performance', 'Congress', 'Search', 'Watchlist', 'Reports', 'Contact'] as const
type Tab = typeof TABS[number]

function getTabFromHash(): Tab {
  const hash = window.location.hash.slice(1).split('/')[0]
  const match = TABS.find(t => t.toLowerCase() === hash.toLowerCase())
  return match || 'Signals'
}

const TAB_GROUPS: { label: string; tabs: Tab[] }[] = [
  { label: 'Markets', tabs: ['Signals', 'Positions', 'Performance'] },
  { label: 'Research', tabs: ['Congress', 'Search', 'Watchlist'] },
  { label: 'More', tabs: ['Reports', 'Contact'] },
]

function App() {
  const [tab, setTab] = useState<Tab>(getTabFromHash)
  const { theme, toggle } = useTheme()

  const switchTab = (t: Tab) => {
    setTab(t)
    window.location.hash = t.toLowerCase()
  }
  const [scanning, setScanning] = useState(false)
  const [scanStep, setScanStep] = useState('')

  // Inactivity logout — 60 minutes
  const logout = useCallback(() => { window.location.href = '/logout' }, [])
  useEffect(() => {
    let timer = setTimeout(logout, 60 * 60 * 1000)
    const reset = () => { clearTimeout(timer); timer = setTimeout(logout, 60 * 60 * 1000) }
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'] as const
    events.forEach(e => window.addEventListener(e, reset))
    return () => { clearTimeout(timer); events.forEach(e => window.removeEventListener(e, reset)) }
  }, [logout])

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: () => fetch('/api/stats').then(r => r.json()),
  })

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await fetch('/api/me')
      if (res.status === 401) {
        window.location.href = '/login'
        return null
      }
      return res.json()
    },
    refetchInterval: 5 * 60 * 1000,
  })

  const triggerScan = async () => {
    setScanning(true)
    setScanStep('Starting scan...')
    const triggerRes = await fetch('/api/scan/trigger', { method: 'POST' })
    if (triggerRes.status === 401) {
      window.location.href = '/login'
      return
    }

    const poll = setInterval(async () => {
      try {
        const res = await fetch('/api/scan/status')
        const data = await res.json()
        setScanStep(data.step || '')
        if (!data.running) {
          clearInterval(poll)
          setScanning(false)
          setScanStep('')
        }
      } catch {
        clearInterval(poll)
        setScanning(false)
        setScanStep('')
      }
    }, 2000)
  }

  return (
    <div className="min-h-screen bg-surface-primary">
      <header className="border-b border-border px-4 sm:px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-content-primary">Trading Signals</h1>
          <p className="text-xs text-content-muted">AI-Powered Market Intelligence</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <button
              onClick={triggerScan}
              disabled={scanning}
              className="bg-green-600 hover:bg-green-500 disabled:bg-surface-tertiary text-white text-sm px-4 py-2 rounded-lg transition"
            >
              {scanning ? 'Scanning...' : 'Run Scan'}
            </button>
            {scanning && scanStep && (
              <p className="text-xs text-content-muted mt-1 max-w-[200px]">{scanStep}</p>
            )}
          </div>
          <button
            onClick={toggle}
            className="p-2 rounded-lg bg-surface-tertiary text-content-muted hover:text-content-primary transition"
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
          <div className="flex items-center gap-2 pl-2 border-l border-border">
            {me?.username && (
              <span className="text-xs text-content-muted hidden sm:inline">{me.username}</span>
            )}
            <a
              href="/logout"
              className="text-xs text-content-faint hover:text-red-400 transition"
              title="Log out"
            >
              Logout
            </a>
          </div>
        </div>
      </header>

      <StatsBar stats={stats} />

      <nav className="px-3 sm:px-6 py-3 border-b border-border">
        <div className="flex flex-wrap gap-1 sm:hidden">
          {TABS.map(t => (
            <button
              key={t}
              onClick={() => switchTab(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                tab === t ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary hover:bg-surface-hover'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="hidden sm:flex items-center gap-1">
          {TAB_GROUPS.map((group, gi) => (
            <div key={group.label} className="flex items-center">
              {gi > 0 && <div className="w-px h-5 bg-border mx-2" />}
              {group.tabs.map(t => (
                <button
                  key={t}
                  onClick={() => switchTab(t)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                    tab === t ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary hover:bg-surface-hover'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          ))}
        </div>
      </nav>

      <main className="px-3 sm:px-6 py-4">
        {tab === 'Signals' && <SignalFeed />}
        {tab === 'Positions' && <OpenPositions />}
        {tab === 'Performance' && <PerformanceTable />}
        {tab === 'Reports' && <ReportsTab />}
        {tab === 'Search' && <StockSearch />}
        {tab === 'Watchlist' && <WatchlistManager />}
        {tab === 'Congress' && <CongressTrades />}
        {tab === 'Contact' && <ContactForm />}
      </main>
    </div>
  )
}

export default App
