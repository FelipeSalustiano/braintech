import { nomeStatus } from '../lib/tipos'
import { pct } from '../lib/util'

export function StBadge({ s }: { s: string }) {
  return <span className={`st s-${s}`}>{nomeStatus(s)}</span>
}

export function ConfBar({ c }: { c: number | null }) {
  if (c == null) return <span className="note">—</span>
  return (
    <span className="conf">
      <span className="b"><i style={{ width: `${Math.round(c * 100)}%` }} /></span>
      {pct(c)}
    </span>
  )
}
