import { useEffect, useRef, useState } from 'react'
import type { Item, Status } from '../lib/tipos'
import { ST, ST_KEYS, temLeitura } from '../lib/tipos'

export function ModalCorrigir({ it, onSalvar, onFechar }: {
  it: Item
  onSalvar: (status: Status, leitura: string, obs: string) => void
  onFechar: () => void
}) {
  // Sugestão com leitura: o caso comum é corrigir o valor. Sem leitura: o caso é conseguir ler o display.
  const [status, setStatus] = useState<Status>(temLeitura(it.status) ? it.status : 'lido')
  const [leitura, setLeitura] = useState(temLeitura(it.status) ? it.leitura ?? '' : '')
  const [obs, setObs] = useState('')
  const campo = useRef<HTMLInputElement>(null)
  const sel = useRef<HTMLSelectElement>(null)
  const pede = temLeitura(status)
  const bloqueado = pede && !/\d/.test(leitura)

  useEffect(() => {
    if (pede) { campo.current?.focus(); campo.current?.select() } else sel.current?.focus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const salvar = () => { if (!bloqueado) onSalvar(status, pede ? leitura.trim() : '—', obs) }

  return (
    <div className="ov">
      <div className="modal sketch" role="dialog" aria-label="Corrigir">
        <h2>Corrigir</h2>
        <label htmlFor="cs">Status correto</label>
        <select id="cs" ref={sel} value={status} onChange={e => { setStatus(e.target.value as Status); setTimeout(() => campo.current?.focus()) }}>
          {ST_KEYS.map(s => <option key={s} value={s}>{ST[s].nome}</option>)}
        </select>
        {pede && <>
          <label htmlFor="cl">Leitura correta</label>
          <input id="cl" ref={campo} inputMode="numeric" value={leitura} placeholder="valor que aparece no display"
            onChange={e => setLeitura(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); salvar() } }} />
        </>}
        {!pede && <div className="hint">{status === 'ilegivel' ? 'Sem leitura: a foto vai para pedido de nova foto.' : 'Sem leitura: o display não aparece na foto.'}</div>}
        <label htmlFor="co">Observação (opcional)</label>
        <textarea id="co" rows={2} value={obs} onChange={e => setObs(e.target.value)} />
        <div className="actions" style={{ marginTop: 14 }}>
          <button className="btn primary" disabled={bloqueado} onClick={salvar}>Salvar correção</button>
          <button className="btn" onClick={onFechar}>Cancelar</button>
        </div>
      </div>
    </div>
  )
}

export function ModalRecusar({ quantos, onRecusar, onFechar }: {
  quantos: number
  onRecusar: (obs: string) => void
  onFechar: () => void
}) {
  const [obs, setObs] = useState('')
  return (
    <div className="ov">
      <div className="modal sketch" role="dialog" aria-label="Recusar">
        <h2>{quantos > 1 ? `Recusar ${quantos} sugestões` : 'Recusar sugestão'}</h2>
        <div className="note">{quantos > 1 ? 'As fotos selecionadas voltam para análise.' : 'A foto volta para análise.'}</div>
        <label htmlFor="ro">Motivo (opcional)</label>
        <textarea id="ro" rows={2} autoFocus value={obs} onChange={e => setObs(e.target.value)}
          placeholder="ex.: leitura não confere com o display" />
        <div className="actions" style={{ marginTop: 14 }}>
          <button className="btn primary" onClick={() => onRecusar(obs)}>Recusar</button>
          <button className="btn" onClick={onFechar}>Cancelar</button>
        </div>
      </div>
    </div>
  )
}
