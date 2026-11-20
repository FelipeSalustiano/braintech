import type { LoteResumo } from '../lib/tipos'
import { ST, ST_KEYS } from '../lib/tipos'
import { fmt } from '../lib/util'

export function Lotes({ participante, lotes, feitosPorLote, onAbrir }: {
  participante: string
  lotes: LoteResumo[]
  feitosPorLote: Map<string, number>
  onAbrir: (lote: LoteResumo) => void
}) {
  return (
    <>
      <h1>Olá, {participante}</h1>
      <div className="note">Lotes disponíveis para validação</div>
      {lotes.length === 0 && (
        <div className="lote sketch"><div className="note">Nenhum lote carregado. Rode <code>python scripts/supabase_carregar.py</code> (veja o README).</div></div>
      )}
      {lotes.map(L => {
        const tot = L.total, feitos = feitosPorLote.get(L.id) ?? 0
        const situ = feitos === 0 ? 'Aguardando validação' : feitos < tot ? 'Em andamento' : 'Concluído'
        return (
          <div className="lote sketch" key={L.id}>
            <div>
              <div className="t">{L.nome}</div>
              <div className="m">{fmt(tot)} fotos · {situ} · {fmt(feitos)}/{fmt(tot)} validadas · {fmt(L.diverge)} leituras divergem do PDA</div>
              <div className="chips" style={{ margin: '12px 0 0' }}>
                {ST_KEYS.map(s => <span className="chip" key={s}>{ST[s].nome} · <b>{fmt(L[s])}</b></span>)}
              </div>
              <div className="prog"><i style={{ width: `${tot ? Math.round(feitos / tot * 100) : 0}%` }} /></div>
            </div>
            <button className={`btn ${feitos < tot ? 'primary' : ''}`} onClick={() => onAbrir(L)}>
              {feitos === 0 ? 'Iniciar validação' : feitos < tot ? 'Continuar' : 'Ver lote'} →
            </button>
          </div>
        )
      })}
    </>
  )
}
