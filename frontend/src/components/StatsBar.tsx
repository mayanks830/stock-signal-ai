interface Stats {
  total_signals: number
  win_count: number
  loss_count: number
  win_rate: number
  avg_win_pct: number
  avg_loss_pct: number
}

export default function StatsBar({ stats }: { stats?: Stats }) {
  if (!stats) return null
  return (
    <div className="flex gap-2 sm:gap-4 px-3 sm:px-6 py-3 bg-surface-secondary border-b border-border overflow-x-auto">
      <Stat label="Total Signals" value={stats.total_signals} />
      <Stat label="Win Rate" value={`${stats.win_rate}%`} color={stats.win_rate >= 50 ? 'text-green-400' : 'text-red-400'} />
      <Stat label="Avg Win" value={`+${stats.avg_win_pct}%`} color="text-green-400" />
      <Stat label="Avg Loss" value={`${stats.avg_loss_pct}%`} color="text-red-400" />
      <Stat label="Wins / Losses" value={`${stats.win_count} / ${stats.loss_count}`} />
    </div>
  )
}

function Stat({ label, value, color = 'text-content-primary' }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="min-w-fit">
      <div className="text-xs text-content-faint">{label}</div>
      <div className={`text-sm font-semibold ${color}`}>{value}</div>
    </div>
  )
}
