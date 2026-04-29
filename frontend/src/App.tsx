import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTheme } from './hooks/useTheme'
import SignalFeed from './components/SignalFeed'
import Portfolio from './components/Portfolio'
import StockSearch from './components/StockSearch'
import WatchlistManager from './components/WatchlistManager'
import CongressTrades from './components/CongressTrades'
import StatsBar from './components/StatsBar'
import FeedbackModal from './components/FeedbackModal'

const TAB_CONFIG = [
  { id: 'picks', label: 'AI Picks', icon: '\u2728', subtitle: 'Daily AI-generated buy signals' },
  { id: 'trades', label: 'My Trades', icon: '\uD83D\uDCBC', subtitle: 'Your open positions & trade history' },
  { id: 'congress', label: 'Congress Trades', icon: '\uD83C\uDFDB\uFE0F', subtitle: 'What politicians are trading' },
  { id: 'lookup', label: 'Stock Lookup', icon: '\uD83D\uDD0D', subtitle: 'Research any ticker with AI' },
  { id: 'watchlist', label: 'Watchlist', icon: '\u2B50', subtitle: 'Stocks you\'re watching' },
] as const

type TabId = typeof TAB_CONFIG[number]['id']

function getTabFromHash(): TabId {
  const hash = window.location.hash.slice(1).split('/')[0].toLowerCase()
  const match = TAB_CONFIG.find(t => t.id === hash)
  return match?.id || 'picks'
}

function App() {
  const [tab, setTab] = useState<TabId>(getTabFromHash)
  const { theme, toggle } = useTheme()
  const [reportsOpen, setReportsOpen] = useState(false)
  const [feedbackOpen, setFeedbackOpen] = useState(false)

  const currentTab = TAB_CONFIG.find(t => t.id === tab)!

  const switchTab = (id: TabId) => {
    setTab(id)
    window.location.hash = id
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

  // Close reports dropdown on outside click
  useEffect(() => {
    if (!reportsOpen) return
    const close = () => setReportsOpen(false)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [reportsOpen])

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

  const { data: reports } = useQuery({
    queryKey: ['reports'],
    queryFn: () => fetch('/api/reports').then(r => r.json()),
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

          {/* Reports dropdown */}
          <div className="relative">
            <button
              onClick={e => { e.stopPropagation(); setReportsOpen(!reportsOpen) }}
              className="p-2 rounded-lg bg-surface-tertiary text-content-muted hover:text-content-primary transition"
              title="Download reports"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </button>
            {reportsOpen && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-surface-secondary border border-border rounded-lg shadow-xl z-50 py-1">
                {reports?.length > 0 ? (
                  reports.map((r: any) => (
                    <a
                      key={r.filename}
                      href={`/api/reports/${r.filename}`}
                      className="block px-3 py-2 text-xs text-content-secondary hover:bg-surface-hover transition"
                      onClick={e => e.stopPropagation()}
                    >
                      {r.filename}
                      <span className="block text-content-faint text-[10px]">{r.size}</span>
                    </a>
                  ))
                ) : (
                  <div className="px-3 py-2 text-xs text-content-faint">No reports available</div>
                )}
              </div>
            )}
          </div>

          {/* Feedback button */}
          <button
            onClick={() => setFeedbackOpen(true)}
            className="p-2 rounded-lg bg-surface-tertiary text-content-muted hover:text-content-primary transition"
            title="Send feedback"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </button>

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
        <div className="flex flex-wrap gap-1">
          {TAB_CONFIG.map(t => (
            <button
              key={t.id}
              onClick={() => switchTab(t.id)}
              className={`flex items-center gap-1.5 px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-medium transition ${
                tab === t.id ? 'bg-blue-600 text-white' : 'text-content-muted hover:text-content-primary hover:bg-surface-hover'
              }`}
            >
              <span className="text-sm sm:text-base leading-none">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Page subtitle */}
      <div className="px-3 sm:px-6 pt-4 pb-1">
        <p className="text-xs text-content-faint">{currentTab.subtitle}</p>
      </div>

      <main className="px-3 sm:px-6 py-3">
        {tab === 'picks' && <SignalFeed />}
        {tab === 'trades' && <Portfolio />}
        {tab === 'lookup' && <StockSearch />}
        {tab === 'watchlist' && <WatchlistManager />}
        {tab === 'congress' && <CongressTrades />}
      </main>

      {feedbackOpen && <FeedbackModal onClose={() => setFeedbackOpen(false)} username={me?.username} />}
    </div>
  )
}

export default App
