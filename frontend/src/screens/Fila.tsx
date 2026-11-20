import { useEffect, useRef, useState } from 'react'
import type { Decisao, Filtro, Item, LoteResumo, Ordem } from '../lib/tipos'
import { ACAO_TXT, CMP_TXT, ST, ST_KEYS } from '../lib/tipos'
import { fmt } from '../lib/util'
import { useUrls } from '../lib/useUrls'
import { ConfBar, StBadge } from './Comuns'

export const PAGE = 50

export interface FilaEstado {
  filtro: Filtro
  diverge: boolean
  busca: string
  ordem: Ordem
  pag: number
  sel: Set<number>
}

export function Fila({ lote, itens, vis, decisoes, f, setF, toast, onAbrir, onLotes, onFim, onAceitarMassa, onRecusarMassa }: {
  lote: LoteResumo
  itens: Item[]
  vis: Item[]
  decisoes: Map<number, Decisao>
  f: FilaEstado
  setF: (patch: Partial<FilaEstado>) => void
  toast: string | null
  onAbrir: (indiceNoFiltro: number) => void
  onLotes: () => void
  onFim: () => void
  onAceitarMassa: (its: Item[]) => void
  onRecusarMassa: (its: Item[]) => void
}) {
  const cont = Object.fromEntries(ST_KEYS.map(s => [s, itens.filter(it => it.status === s).length]))
  const feitos = itens.filter(it => decisoes.has(it.id)).length
  const pags = Math.max(1, Math.ceil(vis.length / PAGE))
  const pag = Math.min(f.pag, pags - 1)
  const pg = vis.slice(pag * PAGE, (pag + 1) * PAGE)
  const allSel = pg.length > 0 && pg.every(it => f.sel.has(it.id))
  const n = f.sel.size
  const urls = useUrls(pg.map(it => it.recorte_path))

  // busca com espera de 250 ms, como no protótipo
  const [busca, setBusca] = useState(f.busca)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => {
    clearTimeout(timer.current)
    timer.current = window.setTimeout(() => { if (busca.trim() !== f.busca) setF({ busca: busca.trim(), pag: 0 }) }, 250)
    return () => clearTimeout(timer.current)
  }, [busca, f.busca, setF])

  const toggle = (id: number) => {
    const s = new Set(f.sel); if (s.has(id)) s.delete(id); else s.add(id); setF({ sel: s })
  }
  const toggleAll = (on: boolean) => {
    const s = new Set(f.sel); pg.forEach(it => on ? s.add(it.id) : s.delete(it.id)); setF({ sel: s })
  }
  const selecionados = () => itens.filter(it => f.sel.has(it.id))

  return (
    <>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <button className="btn sm" style={{ marginBottom: 10 }} onClick={onLotes}>← Lotes</button>
          <h1>{lote.nome}</h1>
          <div className="note">{fmt(itens.length)} fotos · {fmt(feitos)} validadas</div>
        </div>
        <button className={`btn ${feitos === itens.length ? 'primary' : ''}`} onClick={onFim}>Encerrar lote</button>
      </div>

      <div className="chips">
        <button className={`chip ${!f.filtro ? 'on' : ''}`} onClick={() => setF({ filtro: null, pag: 0 })}>Todas · <b>{fmt(itens.length)}</b></button>
        {ST_KEYS.map(s => (
          <button key={s} className={`chip ${f.filtro === s ? 'on' : ''}`} onClick={() => setF({ filtro: s, pag: 0 })}>
            {ST[s].nome} · <b>{fmt(cont[s])}</b>
          </button>
        ))}
        <button className={`chip ${f.filtro === 'pendente' ? 'on' : ''}`} onClick={() => setF({ filtro: 'pendente', pag: 0 })}>
          Pendentes · <b>{fmt(itens.length - feitos)}</b>
        </button>
        <button className={`chip ${f.diverge ? 'on' : ''}`} onClick={() => setF({ diverge: !f.diverge, pag: 0 })}>Só divergentes do PDA</button>
      </div>

      <div className="tools">
        <input type="search" placeholder="Buscar medidor, leitura ou foto" aria-label="Buscar" value={busca} onChange={e => setBusca(e.target.value)} />
        <select aria-label="Ordenar" value={f.ordem} onChange={e => setF({ ordem: e.target.value as Ordem, pag: 0 })}>
          <option value="arquivo">Ordem do lote</option>
          <option value="conf">Menor confiança primeiro</option>
          <option value="confd">Maior confiança primeiro</option>
        </select>
        <span className="note" style={{ alignSelf: 'center' }}>{fmt(vis.length)} fotos no filtro</span>
      </div>

      <div className={`bulk ${n ? 'act' : ''}`}>
        {n ? <>
          <b>{n} {n === 1 ? 'foto selecionada' : 'fotos selecionadas'}</b>
          <button className="btn primary sm" onClick={() => onAceitarMassa(selecionados())}>✓ Aceitar selecionadas</button>
          <button className="btn sm" onClick={() => onRecusarMassa(selecionados())}>✗ Recusar selecionadas</button>
          <button className="btn sm ghost" onClick={() => setF({ sel: new Set() })}>Limpar seleção</button>
        </> : <span className="note">Marque as fotos para aceitar ou recusar em massa.</span>}
        {toast && <span className="toast">{toast}</span>}
      </div>

      <div className="tablewrap">
        <table className="q">
          <thead><tr>
            <th className="ck"><input type="checkbox" checked={allSel} onChange={e => toggleAll(e.target.checked)} aria-label="Selecionar as fotos desta página" /></th>
            <th>Display</th><th>Medidor</th><th>Leitura PDA</th><th>Nota</th><th>Sugestão VoltLens</th><th>Leitura</th><th>Confiança</th><th>vs. PDA</th><th>Situação</th>
          </tr></thead>
          <tbody>
            {pg.length ? pg.map((it, k) => {
              const d = decisoes.get(it.id), c = it.recorte_path ? urls.get(it.recorte_path) : undefined
              return (
                <tr key={it.id} className={`it ${f.sel.has(it.id) ? 'sel' : ''}`} onClick={() => onAbrir(pag * PAGE + k)}>
                  <td className="ck" onClick={e => { e.stopPropagation(); toggle(it.id) }}>
                    <input type="checkbox" checked={f.sel.has(it.id)} readOnly aria-label="Selecionar foto" />
                  </td>
                  <td><div className="thumb">{it.recorte_path ? (c ? <img loading="lazy" src={c} alt="" /> : null) : <span className="empty">sem recorte</span>}</div></td>
                  <td className="mono">{it.medidor || '—'}</td>
                  <td className="mono">{it.leitura_pda || '—'}</td>
                  <td>{it.nota || '—'}</td>
                  <td><StBadge s={it.status} /></td>
                  <td className="mono"><b>{it.leitura || '—'}</b></td>
                  <td><ConfBar c={it.confianca} /></td>
                  <td><span className={`cmp ${it.cmp_pda}`}>{CMP_TXT[it.cmp_pda]}</span></td>
                  <td className="done">{d ? ACAO_TXT[d.acao] + (d.modo === 'em massa' ? ' · massa' : '') : 'Pendente'}</td>
                </tr>
              )
            }) : <tr><td colSpan={10} className="note" style={{ textAlign: 'center', padding: 30 }}>Nenhuma foto neste filtro.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="pager">
        <button className="btn sm" disabled={pag === 0} onClick={() => setF({ pag: pag - 1 })}>← Anterior</button>
        <span className="note">Página {pag + 1} de {pags}</span>
        <button className="btn sm" disabled={pag >= pags - 1} onClick={() => setF({ pag: pag + 1 })}>Próxima →</button>
      </div>
    </>
  )
}
