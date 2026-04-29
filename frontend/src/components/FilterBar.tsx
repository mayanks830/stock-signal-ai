interface FilterBarProps {
  confidence: string
  onConfidence: (v: string) => void
  outcome: string
  onOutcome: (v: string) => void
  sector: string
  onSector: (v: string) => void
  sectors: string[]
  hideOutcome?: boolean
}

const pill = (active: boolean) =>
  `px-3 py-1 text-xs rounded-full cursor-pointer transition ${
    active
      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
      : 'bg-surface-secondary text-content-muted border border-border-subtle hover:border-border hover:text-content-secondary'
  }`

export default function FilterBar({
  confidence, onConfidence,
  outcome, onOutcome,
  sector, onSector,
  sectors,
  hideOutcome,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 mb-4">
      {/* Confidence */}
      <span className="text-xs text-content-faint mr-1">Confidence:</span>
      {['All', 'HIGH', 'MEDIUM'].map(v => (
        <button key={v} className={pill(confidence === v)} onClick={() => onConfidence(v)}>{v}</button>
      ))}

      <span className="text-border-subtle mx-1">|</span>

      {/* Outcome */}
      {!hideOutcome && (
        <>
          <span className="text-xs text-content-faint mr-1">Status:</span>
          {['All', 'OPEN', 'WIN', 'LOSS'].map(v => (
            <button key={v} className={pill(outcome === v)} onClick={() => onOutcome(v)}>{v}</button>
          ))}
          <span className="text-border-subtle mx-1">|</span>
        </>
      )}

      {/* Sector */}
      <span className="text-xs text-content-faint mr-1">Sector:</span>
      <select
        value={sector}
        onChange={e => onSector(e.target.value)}
        className="text-xs bg-surface-secondary text-content-secondary border border-border-subtle rounded-lg px-2 py-1 outline-none focus:border-blue-500/50"
      >
        <option value="All">All Sectors</option>
        {sectors.map(s => <option key={s} value={s}>{s}</option>)}
      </select>
    </div>
  )
}
